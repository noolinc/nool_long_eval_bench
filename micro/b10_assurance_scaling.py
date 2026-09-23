"""B10 b10_asymptotic: admission cost C(R, S) -- repository size R vs semantic
change surface S, held independent by construction (see b10_fixture.py).

Pre-registered hypothesis (task 3de0ac0d):
  H1  dC/dR ~ 0 at fixed S: for every D, the admission median at the largest R
      is at most 2x the median at the smallest R (FLAT_IN_R_THRESHOLD).
  H2  dC/dS > 0: at fixed R, admission cost rises with the change surface
      (least-squares slope of admission median over envelope size > 0).
  Evidence work (native driver + ghost tests) is measured separately and is
  expected to grow with R because the Go driver is package-wide.

Cells, per R (fixture built once with `nool init`, snapshotted per R under
work/b10_snapshots/ and restored in place on the next run):
  per D in B10_D:
    admission       propose --json --full, [reification] enabled = false
    affected_tests  query affected-tests --format json (selection mode + closure)
    full_propose    propose --json --full, reification on (driver + ghost tests)
    git_control     git commit, go vet ./..., go test <oracle packages>
  once per R:
    unknown_path    admission on a file the index has never seen (status)
    concurrency     N concurrent admission proposes, [steer] enabled
    validate_all    land one --fast knot, then time `nool validate --all`

Every nool call goes through ONE frozen binary (work/bin/nool, a copy of a
released build, never a cargo target dir); its sha is checked before and after
the run and a changed or dirty build invalidates the result (binary_gate).
Outcomes are classified, never inferred from output: a non-zero exit is
`refused` even if JSON was printed, a timeout is `dnf` and never a timing
sample, and only an exact selection counts as O(change) (classify_selection).
Fallback-to-full selections are reported as a rate and kept in the fit.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from common import emit, run, run_split, summarize_ms  # noqa: E402
from b10_fixture import D_LEVELS, generate  # noqa: E402

R_LEVELS = [int(x) for x in os.environ.get("B10_R", "100,1000").split(",") if x]
D_SUBSET = [int(x) for x in os.environ.get("B10_D", ",".join(map(str, D_LEVELS))).split(",") if x != ""]
REPS = int(os.environ.get("B10_REPS", "3"))
TIMEOUT_S = int(os.environ.get("B10_TIMEOUT_S", "300"))
CONCURRENCY_N = int(os.environ.get("B10_N", "4"))
FLAT_IN_R_THRESHOLD = 2.0

BENCH_ROOT = common.REPO_ROOT
FROZEN_BIN = Path(os.environ.get("B10_NOOL_BIN", str(BENCH_ROOT / "work" / "bin" / "nool")))
SNAPSHOT_DIR = BENCH_ROOT / "work" / "b10_snapshots"
# Pinned temp root: never the per-user /var/folders tree (bug f33a225a: the
# /var -> /private/var symlink makes path-keyed state disagree with itself).
TMP_ROOT = Path(os.environ.get("B10_TMP", "/tmp/noolbench_b10"))
FORBIDDEN_TMP_PREFIXES = ("/var/folders/", "/private/var/folders/")


# ---------------------------------------------------------------- guards

def check_temp_root(path) -> Path:
    """Refuse a temp root under /var/folders (as given or once resolved)."""
    p = Path(path)
    for cand in (str(p), str(p.resolve()) if p.exists() else str(p)):
        if any((cand + "/").startswith(pre) for pre in FORBIDDEN_TMP_PREFIXES):
            raise ValueError(f"b10: temp root {cand} is under /var/folders; "
                             f"pin it with B10_TMP (default /tmp/noolbench_b10)")
    return p


def _sha256(path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as e:
        return f"unavailable: {e}"


def binary_identity(binary) -> dict:
    raw = subprocess.run([str(binary), "version", "--json"], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, timeout=30).stdout
    start = raw.find("{")
    build = json.loads(raw[start:]) if start >= 0 else {"unavailable": raw[:200]}
    return {"path": str(binary), "sha256": _sha256(binary), "build": build}


def binary_gate(start: dict, end: dict) -> dict:
    """A result is only valid on a frozen, non-dirty binary that did not
    change under the run. Returns {"valid", "reasons", ...}."""
    reasons = []
    if not re.fullmatch(r"[0-9a-f]{64}", start.get("sha256", "")):
        reasons.append("binary_sha_unavailable")
    if start.get("sha256") != end.get("sha256"):
        reasons.append("binary_changed_during_run")
    build = start.get("build") or {}
    if build.get("dirty") is not False:
        reasons.append("dirty_or_unknown_build")
    if (build.get("git_sha") or "") != ((end.get("build") or {}).get("git_sha") or ""):
        reasons.append("build_sha_changed_during_run")
    if "/target/" in start.get("path", ""):
        reasons.append("mutable_cargo_target_binary")
    return {"valid": not reasons, "reasons": reasons, "start": start, "end": end}


def use_frozen_binary() -> None:
    """Every `nool` in this process and its children resolves to FROZEN_BIN."""
    if not FROZEN_BIN.is_file():
        raise SystemExit(
            f"b10: frozen binary {FROZEN_BIN} missing. Freeze a released build first:\n"
            f"  mkdir -p work/bin && cp \"$(command -v nool)\" work/bin/.nool.tmp && "
            f"mv -f work/bin/.nool.tmp work/bin/nool")
    bindir = str(FROZEN_BIN.parent.resolve())
    for env in (os.environ, common.ENV):
        env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    if Path(shutil.which("nool") or "").resolve() != FROZEN_BIN.resolve():
        raise SystemExit(f"b10: PATH does not resolve nool to {FROZEN_BIN}")


# ---------------------------------------------------------------- scoring

def classify_outcome(code, stdout, timed_out, need_signal=True) -> str:
    """landed | refused | dnf | no_signal. Exit code first: a refusal that
    still printed JSON is a refusal, never a landing."""
    if timed_out:
        return "dnf"
    if code != 0:
        return "refused"
    if need_signal and parse_json_lines(stdout).get("semantic_signal") is None:
        return "no_signal"
    return "landed"


def classify_selection(sel: dict | None, expected: int) -> str:
    """exact | full_fallback | empty | mismatch | unparsed. Only `exact`
    counts as an O(change) selection; an empty list is never one."""
    if not sel:
        return "unparsed"
    if sel.get("mode") == "full" or sel.get("run_all"):
        return "full_fallback"
    n = len(sel.get("tests") or [])
    if n == 0:
        return "empty"
    return "exact" if n == expected else "mismatch"


def outcome_counts(samples) -> dict:
    out = {"landed": 0, "refused": 0, "dnf": 0, "no_signal": 0}
    for s in samples:
        out[s.get("outcome", "no_signal")] = out.get(s.get("outcome", "no_signal"), 0) + 1
    return out


def timing(samples) -> dict | None:
    """summarize_ms over landed samples only (refused/dnf never enter)."""
    return summarize_ms([s["wall_ms"] for s in samples
                         if s.get("outcome") == "landed" and s.get("wall_ms") is not None])


def ratio(hi, lo):
    return round(hi / lo, 2) if (hi is not None and lo) else None


def ols_slope(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den, 4) if den else None


def score(by_r: dict) -> dict:
    """Pre-registered ratios. Cells whose closure check failed (mismatch,
    empty, unparsed selection or wrong envelope) are excluded and listed;
    full-selection fallbacks stay in and are counted."""
    rs = sorted(int(r) for r in by_r)
    out = {"flat_in_R_threshold": FLAT_IN_R_THRESHOLD, "by_d": {}, "by_r": {}, "excluded": []}
    ds = sorted({int(d) for r in by_r.values() for d in r["by_d"]})
    for d in ds:
        meds = {}
        for r in rs:
            e = by_r[str(r)]["by_d"].get(str(d))
            if not e:
                continue
            if not e["closure"]["ok"]:
                out["excluded"].append({"R": r, "D": d, "reason": e["closure"]["reason"]})
                continue
            meds[r] = {k: (e[k + "_ms"] or {}).get("median_ms")
                       for k in ("admission", "affected_tests", "full_propose")}
            meds[r]["git_vet"] = (e["git_control"].get("vet_ms") or {}).get("median_ms")
        entry = {"medians_by_R": meds}
        if len(meds) >= 2:
            lo, hi = min(meds), max(meds)
            entry["R_lo"], entry["R_hi"] = lo, hi
            for k in ("admission", "affected_tests", "full_propose", "git_vet"):
                entry[f"{k}_ratio_hi_over_lo"] = ratio(meds[hi][k], meds[lo][k])
            a = entry["admission_ratio_hi_over_lo"]
            entry["admission_flat_in_R"] = (a <= FLAT_IN_R_THRESHOLD) if a is not None else None
        else:
            entry["admission_flat_in_R"] = None  # never fabricated from one point
        out["by_d"][str(d)] = entry
    for r in rs:
        pts = []
        for d, e in by_r[str(r)]["by_d"].items():
            m = (e.get("admission_ms") or {}).get("median_ms")
            env = e.get("envelope_observed")
            if e["closure"]["ok"] and m is not None and env is not None:
                pts.append((env, m))
        pts.sort()
        slope = ols_slope([p[0] for p in pts], [p[1] for p in pts])
        out["by_r"][str(r)] = {
            "admission_vs_envelope_points": pts,
            "admission_ms_per_envelope_file": slope,
            "dC_dS_positive": (slope > 0) if slope is not None else None,
            "admission_ratio_Dmax_over_Dmin": ratio(pts[-1][1], pts[0][1]) if len(pts) >= 2 else None,
        }
    flats = [e["admission_flat_in_R"] for e in out["by_d"].values()]
    slopes = [e["dC_dS_positive"] for e in out["by_r"].values()]
    out["H1_flat_in_R_all_D"] = all(flats) if flats and None not in flats else None
    out["H2_dC_dS_positive_all_R"] = all(slopes) if slopes and None not in slopes else None
    return out


# ---------------------------------------------------------------- runners

def parse_json_lines(stdout: str) -> dict:
    found = {}
    for line in stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("semantic_signal", "proposal_stages"):
            if key in obj:
                found[key] = obj[key]
    return found


def timed(cmd, ws, timeout=None, env=None):
    """run_split, with a timeout turned into a dnf record (never a sample)."""
    try:
        if env is None:
            code, out, err, ms = run_split(cmd, ws, timeout=timeout or TIMEOUT_S)
        else:
            t0 = time.monotonic()
            p = subprocess.run(cmd, cwd=str(ws), env=env, timeout=timeout or TIMEOUT_S,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            code, out, err, ms = p.returncode, p.stdout, p.stderr, (time.monotonic() - t0) * 1000
        return {"code": code, "stdout": out, "stderr": err, "wall_ms": round(ms, 2), "timed_out": False}
    except subprocess.TimeoutExpired:
        return {"code": None, "stdout": "", "stderr": "", "wall_ms": None, "timed_out": True}


def reinit_lightweight_git(ws: Path) -> None:
    run(["git", "init", "-q", "-b", "main"], ws, check=True)
    run(["git", "config", "user.email", "b10@nool-benchmarks.local"], ws, check=True)
    run(["git", "config", "user.name", "B10"], ws, check=True)
    run(["git", "add", "-A"], ws, check=True)
    code, out, _ = run(["git", "commit", "-qm", "b10 fixture baseline"], ws)
    if code != 0:
        raise RuntimeError(f"baseline commit failed:\n{out}")


def nool_init(ws: Path) -> float:
    t0 = time.monotonic()
    code, out, _ = run(["nool", "init"], ws, timeout=int(os.environ.get("B10_INIT_TIMEOUT_S", "3600")))
    if code != 0:
        raise RuntimeError(f"nool init failed:\n{out[-2000:]}")
    return time.monotonic() - t0


def set_toml(ws: Path, section: str, key: str, value: str) -> None:
    """Replace `key = ...` inside `[section]`; fail loudly if the shape changed."""
    path = ws / "nool.toml"
    text = path.read_text()
    pat = re.compile(rf"(^\[{re.escape(section)}\]\n(?:(?!^\[).*\n)*?){re.escape(key)} = [^\n]*", re.M)
    text2, n = pat.subn(rf"\g<1>{key} = {value}", text, count=1)
    if n != 1:
        raise RuntimeError(f"nool.toml: [{section}] {key} not found -- config shape changed")
    path.write_text(text2)


def attach_contracts(ws: Path, d_levels) -> None:
    """One [attestation.obligations] row per target cluster, so every change
    surface carries a recorded contract (envelope.contracts is non-empty)."""
    path = ws / "nool.toml"
    text = path.read_text()
    rows = "".join(f'"t{d}/**" = ["unit-tests"]\n' for d in d_levels)
    if "[attestation.obligations]\n" not in text:
        raise RuntimeError("nool.toml: [attestation.obligations] missing -- config shape changed")
    path.write_text(text.replace("[attestation.obligations]\n", "[attestation.obligations]\n" + rows, 1))


def configure(ws: Path, reification: bool, steer: bool = False) -> None:
    set_toml(ws, "reification", "enabled", "true" if reification else "false")
    set_toml(ws, "steer", "enabled", "true" if steer else "false")


def fixture_key(r: int) -> str:
    src = (Path(__file__).resolve().parent / "b10_fixture.py").read_bytes()
    h = hashlib.sha256(src + f"|{r}|{sorted(D_SUBSET)}|{_sha256(FROZEN_BIN)}|v2".encode())
    return h.hexdigest()[:16]


def build_or_restore(ws: Path, r: int) -> dict:
    """Build the R fixture once, snapshot it (tree + .nool ledger), restore
    it in place on later runs. The snapshot is keyed by fixture source, R,
    D set and binary sha, so a new binary or fixture always rebuilds."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snap = SNAPSHOT_DIR / f"r{r}_{fixture_key(r)}.tar"
    meta = snap.with_suffix(".json")
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    if snap.exists() and meta.exists():
        t0 = time.monotonic()
        with tarfile.open(snap) as tf:
            tf.extractall(ws)  # our own snapshot, written by build_or_restore
        manifest = json.loads(meta.read_text())
        manifest["restored_from_snapshot"] = snap.name
        manifest["restore_s"] = round(time.monotonic() - t0, 1)
        return manifest
    manifest = generate(ws, r, d_levels=tuple(D_SUBSET))
    reinit_lightweight_git(ws)
    manifest["init_s"] = round(nool_init(ws), 1)
    set_toml(ws, "gating", "blast_block_threshold", "1000000")
    attach_contracts(ws, D_SUBSET)
    configure(ws, reification=False)
    with tarfile.open(snap, "w") as tf:
        tf.add(ws, arcname=".")
    meta.write_text(json.dumps(manifest, indent=1) + "\n")
    manifest["restored_from_snapshot"] = None
    return manifest


def touch(ws: Path, path: str) -> None:
    with (ws / path).open("a") as fh:
        fh.write("// b10 probe\n")


def reset(ws: Path, path: str) -> None:
    run(["git", "checkout", "--", path], ws, check=True)


def active_leases(ws: Path) -> int | None:
    code, out, _ = run(["nool", "announce", "status", "--json"], ws, timeout=60)
    start = out.find("{")
    try:
        return len(json.loads(out[start:]).get("leases") or []) if code == 0 and start >= 0 else None
    except json.JSONDecodeError:
        return None


def abort_candidates(ws: Path, agent_ids=()) -> None:
    """Discard the candidate AND the exclusive lease propose filed: `propose
    --abort` leaves the lease live for its TTL (see leases_after_abort), and
    a leftover lease would turn the next cell into a coordination conflict."""
    run(["nool", "propose", "--abort"], ws, timeout=60)
    run(["nool", "candidate", "clear"], ws, timeout=60)
    run(["nool", "announce", "release", "--all"], ws, timeout=60)
    for a in agent_ids:
        run(["nool", "announce", "release", "--all", "--agent-id", a], ws, timeout=60)


def propose_json(ws: Path, paths, intent, env=None) -> dict:
    cmd = ["nool", "propose", "--path", *paths, "--intent", intent,
           "--json", "--full", "--auto-justify"]
    t = timed(cmd, ws, env=env)
    parsed = parse_json_lines(t["stdout"])
    sig = parsed.get("semantic_signal") or {}
    br = sig.get("blast_radius") or {}
    plan = (sig.get("evidence_plan") or {}).get("plan")
    return {
        "outcome": classify_outcome(t["code"], t["stdout"], t["timed_out"]),
        "exit_code": t["code"], "wall_ms": t["wall_ms"],
        "envelope": br.get("affected"), "envelope_status": br.get("status"),
        "contracts_count": len((sig.get("envelope") or {}).get("contracts") or []) if sig else None,
        "plan": next(iter(plan)) if isinstance(plan, dict) else plan,
        "stages": parsed.get("proposal_stages"),
        "stderr_tail": t["stderr"][-300:] if t["code"] not in (0, None) else "",
    }


def measure_admission(ws: Path, d: int, rep: int) -> dict:
    tfile = f"t{d}/t{d}.go"
    touch(ws, tfile)
    try:
        return propose_json(ws, [tfile], f"b10 admission D={d} rep={rep}")
    finally:
        abort_candidates(ws)
        reset(ws, tfile)


def measure_affected_tests(ws: Path, d: int) -> dict:
    t = timed(["nool", "query", "affected-tests", "--paths", f"t{d}/t{d}.go", "--format", "json"], ws)
    sel = None
    if t["code"] == 0:
        start = t["stdout"].find("{")
        try:
            sel = json.loads(t["stdout"][start:]) if start >= 0 else None
        except json.JSONDecodeError:
            sel = None
    outcome = classify_outcome(t["code"], t["stdout"], t["timed_out"], need_signal=False)
    return {"outcome": outcome if sel is not None or outcome != "landed" else "no_signal",
            "exit_code": t["code"], "wall_ms": t["wall_ms"],
            "mode": (sel or {}).get("mode"), "reason": (sel or {}).get("reason"),
            "tests": [x.get("path") for x in (sel or {}).get("tests") or []],
            "_sel": sel}


def measure_full_propose(ws: Path, d: int, rep: int) -> dict:
    configure(ws, reification=True)
    tfile = f"t{d}/t{d}.go"
    touch(ws, tfile)
    try:
        return propose_json(ws, [tfile], f"b10 full D={d} rep={rep}")
    finally:
        abort_candidates(ws)
        reset(ws, tfile)
        configure(ws, reification=False)


def oracle_packages(d: int) -> list[str]:
    return [f"./t{d}"] + [f"./t{d}_dep_{j}" for j in range(d)]


def measure_git_controls(ws: Path, d: int, reps: int) -> dict:
    tfile = f"t{d}/t{d}.go"
    commit, vet, oracle, exits = [], [], [], []
    for _ in range(reps):
        touch(ws, tfile)
        c1 = timed(["git", "commit", "-aqm", f"b10 git control D={d}"], ws)
        c2 = timed(["go", "vet", "./..."], ws)
        c3 = timed(["go", "test", "-count=1", *oracle_packages(d)], ws)
        run(["git", "reset", "-q", "--hard", "HEAD~1"], ws)
        for c, bucket in ((c1, commit), (c2, vet), (c3, oracle)):
            bucket.append({"outcome": classify_outcome(c["code"], "", c["timed_out"], need_signal=False),
                           "wall_ms": c["wall_ms"]})
        exits.append([c1["code"], c2["code"], c3["code"]])
    return {"commit_ms": timing(commit), "vet_ms": timing(vet), "oracle_test_ms": timing(oracle),
            "counts": {"commit": outcome_counts(commit), "vet": outcome_counts(vet),
                       "oracle_test": outcome_counts(oracle)},
            "exits": exits}


def measure_unknown_path(ws: Path, reps: int) -> dict:
    samples = []
    for rep in range(reps):
        p = ws / "u_new" / "u.go"
        p.parent.mkdir(exist_ok=True)
        p.write_text("package u_new\n\nfunc U() int {\n\treturn 7\n}\n")
        try:
            samples.append(propose_json(ws, ["u_new/u.go"], f"b10 unknown-path rep={rep}"))
        finally:
            abort_candidates(ws)
            shutil.rmtree(p.parent, ignore_errors=True)
    return {"samples": samples, "counts": outcome_counts(samples), "wall_ms": timing(samples),
            "status_counts": _counts(s["envelope_status"] for s in samples),
            "plan_counts": _counts(s["plan"] for s in samples)}


def measure_concurrency(ws: Path, n: int) -> dict:
    """N concurrent admission proposes on distinct targets, each under its
    own agent id, with [steer] enabled. Contention (exit 3) is recorded as
    refused, never as a landing."""
    configure(ws, reification=False, steer=True)
    targets = [f"t{D_SUBSET[i % len(D_SUBSET)]}/t{D_SUBSET[i % len(D_SUBSET)]}.go" for i in range(n)]
    targets = list(dict.fromkeys(targets))  # distinct files only
    for t in targets:
        touch(ws, t)
    try:
        def one(i_t):
            i, t = i_t
            env = dict(common.ENV, NOOL_AGENT_ID=f"b10-conc-{i}")
            return propose_json(ws, [t], f"b10 concurrency {i}", env=env)
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=len(targets)) as ex:
            samples = list(ex.map(one, enumerate(targets)))
        batch_ms = round((time.monotonic() - t0) * 1000, 2)
    finally:
        abort_candidates(ws, agent_ids=[f"b10-conc-{i}" for i in range(len(targets))])
        for t in targets:
            reset(ws, t)
        configure(ws, reification=False, steer=False)
    for s in samples:
        s.pop("stages", None)
    return {"n": len(targets), "steer": True, "batch_wall_ms": batch_ms,
            "samples": samples, "counts": outcome_counts(samples), "wall_ms": timing(samples)}


def measure_validate_all(ws: Path, d: int) -> dict:
    """Land one --fast knot (deferred validation), then time validate --all.
    Mutates the ledger, so it runs last for this R."""
    tfile = f"t{d}/t{d}.go"
    touch(ws, tfile)
    land = timed(["nool", "propose", "--path", tfile, "--intent", "b10 fast landing",
                  "--fast", "--solidify", "--auto-justify", "--compact"], ws)
    land_outcome = classify_outcome(land["code"], land["stdout"], land["timed_out"], need_signal=False)
    val = timed(["nool", "validate", "--all", "--compact"], ws)
    val_outcome = classify_outcome(val["code"], val["stdout"], val["timed_out"], need_signal=False)
    return {"fast_land": {"outcome": land_outcome, "wall_ms": land["wall_ms"]},
            "validate_all": {"outcome": val_outcome, "wall_ms": val["wall_ms"],
                             "tail": (val["stdout"] + val["stderr"])[-300:]}}


def _counts(items) -> dict:
    out = {}
    for it in items:
        out[str(it)] = out.get(str(it), 0) + 1
    return out


def closure_check(manifest: dict, d: int, sel_class: str, admission) -> dict:
    gt = manifest["ground_truth"][str(d)]
    envs = {a["envelope"] for a in admission if a["outcome"] == "landed"}
    env_ok = envs == {gt["envelope_expected"]}
    if sel_class not in ("exact", "full_fallback"):
        return {"ok": False, "reason": f"selection_{sel_class}", "envelope_values": sorted(envs)}
    if not env_ok:
        return {"ok": False, "reason": "envelope_mismatch", "envelope_values": sorted(envs)}
    return {"ok": True, "reason": None, "envelope_values": sorted(envs)}


def run_r(ws: Path, r: int) -> dict:
    t0 = time.monotonic()
    manifest = build_or_restore(ws, r)
    print(f"  fixture: {manifest['total_packages']} packages, {manifest['total_files']} files, "
          f"init {manifest.get('init_s')}s, snapshot={manifest.get('restored_from_snapshot')} "
          f"({time.monotonic() - t0:.1f}s)")
    res = {"manifest": manifest, "by_d": {}}
    # Probe once: does `propose --abort` release the lease propose filed?
    tprobe = f"t{D_SUBSET[0]}/t{D_SUBSET[0]}.go"
    touch(ws, tprobe)
    run(["nool", "propose", "--path", tprobe, "--intent", "b10 lease probe", "--json", "--full",
         "--auto-justify"], ws, timeout=TIMEOUT_S)
    run(["nool", "propose", "--abort"], ws, timeout=60)
    res["leases_after_abort"] = active_leases(ws)
    abort_candidates(ws)
    reset(ws, tprobe)
    res["leases_after_release"] = active_leases(ws)
    print(f"  leases live after propose --abort: {res['leases_after_abort']} "
          f"(after announce release --all: {res['leases_after_release']})")
    for d in D_SUBSET:
        gt = manifest["ground_truth"][str(d)]
        sel_samples = [measure_affected_tests(ws, d) for _ in range(REPS)]
        sel_class = classify_selection(sel_samples[0].pop("_sel"), gt["affected_tests_expected"])
        for s in sel_samples[1:]:
            s.pop("_sel", None)
        admission = [measure_admission(ws, d, rep) for rep in range(REPS)]
        full = [measure_full_propose(ws, d, rep) for rep in range(REPS)]
        git_ctrl = measure_git_controls(ws, d, REPS)
        closure = closure_check(manifest, d, sel_class, admission)
        envs = [a["envelope"] for a in admission if a["outcome"] == "landed"]
        entry = {
            "closure": closure, "selection_class": sel_class,
            "o_change_selection": sel_class == "exact",
            "affected_tests_expected": gt["affected_tests_expected"],
            "envelope_expected": gt["envelope_expected"],
            "envelope_observed": envs[0] if envs else None,
            "affected_tests": sel_samples, "affected_tests_ms": timing(sel_samples),
            "affected_tests_counts": outcome_counts(sel_samples),
            "admission": admission, "admission_ms": timing(admission),
            "admission_counts": outcome_counts(admission),
            "full_propose": full, "full_propose_ms": timing(full),
            "full_propose_counts": outcome_counts(full),
            "git_control": git_ctrl,
        }
        res["by_d"][str(d)] = entry
        am, fm = entry["admission_ms"] or {}, entry["full_propose_ms"] or {}
        print(f"  D={d:3d}: sel={sel_class:13s} closure_ok={closure['ok']} env={entry['envelope_observed']} "
              f"admission={am.get('median_ms')}ms {entry['admission_counts']} "
              f"full={fm.get('median_ms')}ms {entry['full_propose_counts']} "
              f"vet={(git_ctrl['vet_ms'] or {}).get('median_ms')}ms")
    res["unknown_path"] = measure_unknown_path(ws, REPS)
    print(f"  unknown_path: status={res['unknown_path']['status_counts']} "
          f"counts={res['unknown_path']['counts']}")
    res["concurrency"] = measure_concurrency(ws, CONCURRENCY_N)
    print(f"  concurrency N={res['concurrency']['n']}: counts={res['concurrency']['counts']} "
          f"batch={res['concurrency']['batch_wall_ms']}ms")
    res["validate_all"] = measure_validate_all(ws, D_SUBSET[min(1, len(D_SUBSET) - 1)])
    print(f"  validate_all: {res['validate_all']['validate_all']['outcome']} "
          f"{res['validate_all']['validate_all']['wall_ms']}ms")
    sels = [e["selection_class"] for e in res["by_d"].values()]
    res["fallback"] = {"cells": len(sels), "full_fallback": sels.count("full_fallback"),
                       "rate": round(sels.count("full_fallback") / len(sels), 3) if sels else None}
    return res


def main():
    if os.environ.get("B10_RESULTS_DIR"):  # sanity runs never overwrite committed results
        common.RESULTS_DIR = Path(os.environ["B10_RESULTS_DIR"]).resolve()
    use_frozen_binary()
    check_temp_root(TMP_ROOT)
    gate_start = binary_identity(FROZEN_BIN)
    print(f"[b10_asymptotic] nool: {FROZEN_BIN} sha256={gate_start['sha256'][:16]} "
          f"build={gate_start['build'].get('version')}/{gate_start['build'].get('git_sha', '')[:8]} "
          f"dirty={gate_start['build'].get('dirty')}")
    print(f"[b10_asymptotic] R={R_LEVELS} D={D_SUBSET} reps={REPS} N={CONCURRENCY_N} tmp={TMP_ROOT}")
    pre = binary_gate(gate_start, gate_start)
    if not pre["valid"] and not os.environ.get("B10_ALLOW_UNFROZEN"):
        raise SystemExit(f"b10: refusing to run on this binary: {pre['reasons']}")

    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    check_temp_root(TMP_ROOT)
    by_r = {}
    try:
        for r in R_LEVELS:
            print(f"\n[b10_asymptotic] === R={r} ===")
            by_r[str(r)] = run_r(TMP_ROOT / f"r{r}", r)
    finally:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    gate = binary_gate(gate_start, binary_identity(FROZEN_BIN))
    scaling = score(by_r)
    all_sel = [e["selection_class"] for r in by_r.values() for e in r["by_d"].values()]
    payload = {
        "part": "b10_asymptotic",
        "config": {"R_levels": R_LEVELS, "D_levels": D_SUBSET, "reps": REPS,
                   "timeout_s": TIMEOUT_S, "concurrency_n": CONCURRENCY_N,
                   "temp_root": str(TMP_ROOT), "admission_mode": "--full --json, [reification] enabled=false",
                   "evidence_mode": "--full --json, [reification] enabled=true",
                   "frozen_binary_source": os.environ.get("B10_NOOL_SOURCE", "~/.local/bin/nool (released install)")},
        "binary_gate": gate,
        "valid": gate["valid"],
        "fallback": {"cells": len(all_sel), "full_fallback": all_sel.count("full_fallback"),
                     "rate": round(all_sel.count("full_fallback") / len(all_sel), 3) if all_sel else None},
        "by_R": by_r,
        "scaling": scaling,
    }
    emit("b10_assurance_scaling", payload)
    print(json.dumps({k: scaling[k] for k in ("H1_flat_in_R_all_D", "H2_dC_dS_positive_all_R", "excluded")},
                     indent=1))
    if not gate["valid"]:
        print(f"[b10_asymptotic] INVALID: {gate['reasons']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
