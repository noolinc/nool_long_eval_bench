"""B10 part 2: admission cost C(R, S) — repository size R vs semantic change
surface S, held independent by construction (see b10_fixture.py).

Claim under test: holding S constant, does admission work (computing the
envelope + deciding evidence) stay ~flat as unrelated repository state R
grows, while genuine per-package evidence work (vet/test) grows with R?

Built via `nool init` (derives the entity graph from the filesystem in one
pass; zero proposal knots, so the fixture's size is never limited by the
knot cap) after a single baseline git commit, mirroring b10_self's
lightweight-git pattern. `[reification] enabled = false` for the admission
cells, per the fast-path fact confirmed this session: --fast on a compiled
file always runs the native driver regardless of that flag, so --full is
the only genuinely gate-only combination.
"""

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import TempRoot, emit, run, run_split, summarize_ms, version_of  # noqa: E402
from b10_fixture import D_LEVELS, generate, target_symbol  # noqa: E402

R_LEVELS = [int(x) for x in os.environ.get("B10_R", "100,1000").split(",") if x]
D_SUBSET = [int(x) for x in os.environ.get("B10_D", ",".join(map(str, D_LEVELS))).split(",") if x != ""]
REPS = int(os.environ.get("B10_REPS", "3"))
TIMEOUT_S = int(os.environ.get("B10_TIMEOUT_S", "120"))


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
    code, out, _ = run(["nool", "init"], ws, timeout=int(os.environ.get("B10_INIT_TIMEOUT_S", "600")))
    if code != 0:
        raise RuntimeError(f"nool init failed:\n{out}")
    return time.monotonic() - t0


def disable_reification(ws: Path) -> None:
    path = ws / "nool.toml"
    text = path.read_text()
    text2 = re.sub(r"(\[reification\]\nenabled = )true", r"\1false", text, count=1)
    if text2 == text and "[reification]" in text:
        raise RuntimeError("disable_reification regex did not match -- nool.toml shape changed")
    path.write_text(text2)


def govern_never_blocking(ws: Path) -> None:
    """Gates evaluate (real admission work happens) but never refuse the
    timed landing: raised blast threshold, no steer/invariant surprises."""
    path = ws / "nool.toml"
    text = path.read_text()
    text = re.sub(r"blast_block_threshold = \d+", "blast_block_threshold = 1000000", text)
    (path).write_text(text)


def build_repo(root: Path, r: int) -> dict:
    manifest = generate(root, r, d_levels=tuple(D_SUBSET))
    reinit_lightweight_git(root)
    manifest["init_s"] = round(nool_init(root), 1)
    disable_reification(root)
    govern_never_blocking(root)
    return manifest


def probe_one(ws: Path, d: int) -> dict:
    """Untimed sanity check: does the graph the fixture built actually
    report the constructed ground truth? Run once per (R, D); a mismatch
    excludes that D from the scoring fit rather than silently trusting it."""
    tfile = f"t{d}/t{d}.go"
    code, out, _ = run(["nool", "query", "affected-tests", "--paths", tfile], ws, timeout=60)
    m = re.search(r"(\d+)/(\d+) test files", out) or re.search(r"^(\d+)\D+(\d+)", out)
    reported = None
    if "test files" in out:
        m2 = re.search(r"(\d+)/\d+ test files", out)
        if m2:
            reported = int(m2.group(1))
    return {"exit": code, "raw": out[:300], "affected_tests_reported": reported}


def touch(ws: Path, path: str) -> None:
    with (ws / path).open("a") as fh:
        fh.write("// b10 probe\n")


def reset(ws: Path, path: str) -> None:
    run(["git", "checkout", "--", path], ws, check=True)


def measure_admission(ws: Path, d: int, rep: int) -> dict:
    """gate_only cell: --full with reification disabled. This is the
    admission-only measurement the C(R, S) claim is about."""
    tfile = f"t{d}/t{d}.go"
    touch(ws, tfile)
    cmd = ["nool", "propose", "--path", tfile, "--intent", f"b10 D={d} rep={rep}",
           "--json", "--full", "--auto-justify"]
    code, stdout, stderr, ms = run_split(cmd, ws, timeout=TIMEOUT_S)
    envelope = contracts = plan = None
    for line in stdout.splitlines():
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "semantic_signal" in obj:
                sig = obj["semantic_signal"]
                envelope = sig["blast_radius"]
                contracts = len(sig["envelope"]["contracts"])
                plan = sig["evidence_plan"]["plan"]
    run(["nool", "propose", "--abort"], ws, timeout=30)
    reset(ws, tfile)
    return {"exit_code": code, "wall_ms": round(ms, 2), "envelope": envelope,
            "contracts_count": contracts, "plan": plan}


def measure_fast_vet(ws: Path, d: int, rep: int) -> dict:
    """fast_vet cell: --fast, still runs `go vet ./...` (confirmed this
    session that --fast does not consult [reification].enabled for a
    compiled file) -- this is the O(package-count) evidence floor."""
    tfile = f"t{d}/t{d}.go"
    touch(ws, tfile)
    cmd = ["nool", "propose", "--path", tfile, "--intent", f"b10 fastvet D={d} rep={rep}",
           "--json", "--fast", "--auto-justify"]
    code, stdout, stderr, ms = run_split(cmd, ws, timeout=TIMEOUT_S)
    run(["nool", "propose", "--abort"], ws, timeout=30)
    reset(ws, tfile)
    return {"exit_code": code, "wall_ms": round(ms, 2)}


def measure_git_controls(ws: Path, d: int) -> dict:
    tfile = f"t{d}/t{d}.go"
    touch(ws, tfile)
    code1, _, ms_commit = run(["git", "commit", "-aqm", f"b10 git control D={d}"], ws)
    code2, _, ms_vet = run(["go", "vet", "./..."], ws, timeout=TIMEOUT_S)
    oracle_paths = [f"./t{d}/...", f"./t{d}_dep_*/..." ] if d > 0 else [f"./t{d}/..."]
    code3, _, ms_oracle = run(["go", "test", *oracle_paths], ws, timeout=TIMEOUT_S)
    run(["git", "reset", "-q", "--hard", "HEAD~1"], ws)
    return {
        "commit_ms": round(ms_commit, 2), "vet_exit": code1 or code2, "vet_ms": round(ms_vet, 2),
        "oracle_exit": code3, "oracle_ms": round(ms_oracle, 2),
    }


def run_cell(name, fn, *args):
    samples = []
    for i, a in enumerate(args):
        try:
            r = fn(*a)
            samples.append(r)
        except Exception as e:  # noqa: BLE001 - recorded, not fatal
            samples.append({"error": str(e)})
    return samples


def main():
    nool_bin = shutil.which("nool")
    if not nool_bin:
        print("ERROR: nool not on PATH", file=sys.stderr)
        sys.exit(1)
    print(f"[b10_asymptotic] nool: {nool_bin}")
    print(f"[b10_asymptotic] nool version: {version_of(['nool', 'version', '--json'])[:150]}")
    print(f"[b10_asymptotic] R levels: {R_LEVELS}, D levels: {D_SUBSET}, reps: {REPS}")

    all_r_results = {}
    with TempRoot("b10asym") as tmp:
        for r in R_LEVELS:
            ws = tmp / f"r{r}"
            print(f"\n[b10_asymptotic] === R={r} ===")
            t0 = time.monotonic()
            manifest = build_repo(ws, r)
            build_s = time.monotonic() - t0
            print(f"  built {manifest['total_packages']} packages "
                  f"({manifest['total_files']} files) in {build_s:.1f}s "
                  f"(nool init: {manifest['init_s']}s)")

            r_result = {"manifest": manifest, "build_seconds": round(build_s, 1), "by_d": {}}
            for d in D_SUBSET:
                probe = probe_one(ws, d)
                expected = manifest["ground_truth"][str(d)]["affected_tests_expected"]
                closure_ok = probe.get("affected_tests_reported") == expected
                print(f"  D={d:3d}: affected_tests probe reported={probe.get('affected_tests_reported')} "
                      f"expected={expected} ok={closure_ok}")

                admission = [measure_admission(ws, d, rep) for rep in range(REPS)]
                fast_vet = [measure_fast_vet(ws, d, rep) for rep in range(REPS)]
                for a in admission:
                    print(f"    gate_only  rep wall={a['wall_ms']}ms exit={a['exit_code']} "
                          f"envelope={a['envelope']['affected'] if a['envelope'] else None} plan={a['plan']}")
                for f in fast_vet:
                    print(f"    fast_vet   rep wall={f['wall_ms']}ms exit={f['exit_code']}")
                git_ctrl = measure_git_controls(ws, d)
                print(f"    git        vet={git_ctrl['vet_ms']}ms oracle={git_ctrl['oracle_ms']}ms")

                r_result["by_d"][str(d)] = {
                    "closure_ok": closure_ok,
                    "probe": probe,
                    "admission": admission,
                    "admission_ms": summarize_ms([a["wall_ms"] for a in admission if a.get("exit_code") == 0]),
                    "fast_vet": fast_vet,
                    "fast_vet_ms": summarize_ms([f["wall_ms"] for f in fast_vet if f.get("exit_code") == 0]),
                    "git_control": git_ctrl,
                }
            all_r_results[str(r)] = r_result

    # Pre-registered scoring: admission is "flat in R" if the largest-R
    # median is at most 2x the smallest-R median, at fixed D. Cells with
    # closure_ok=False are excluded from the fit and listed separately.
    r_sorted = sorted(R_LEVELS)
    scaling = {"flat_in_R_threshold": 2.0, "by_d": {}, "excluded": []}
    for d in D_SUBSET:
        meds = {}
        for r in r_sorted:
            entry = all_r_results[str(r)]["by_d"][str(d)]
            if not entry["closure_ok"]:
                scaling["excluded"].append({"R": r, "D": d, "reason": "closure_mismatch"})
                continue
            am = entry["admission_ms"]
            fv = entry["fast_vet_ms"]
            meds[r] = {
                "admission_median_ms": am["median_ms"] if am else None,
                "fast_vet_median_ms": fv["median_ms"] if fv else None,
            }
        if len(meds) >= 2:
            r_lo, r_hi = min(meds), max(meds)
            adm_lo, adm_hi = meds[r_lo]["admission_median_ms"], meds[r_hi]["admission_median_ms"]
            fv_lo, fv_hi = meds[r_lo]["fast_vet_median_ms"], meds[r_hi]["fast_vet_median_ms"]
            scaling["by_d"][str(d)] = {
                "medians_by_R": meds,
                "admission_ratio_hi_over_lo": round(adm_hi / adm_lo, 2) if adm_lo else None,
                "admission_flat_in_R": (adm_hi / adm_lo) <= 2.0 if adm_lo else None,
                "fast_vet_ratio_hi_over_lo": round(fv_hi / fv_lo, 2) if fv_lo else None,
            }

    payload = {
        "config": {"R_levels": R_LEVELS, "D_levels": D_SUBSET, "reps": REPS, "timeout_s": TIMEOUT_S},
        "by_R": all_r_results,
        "scaling": scaling,
    }
    emit("b10_assurance_scaling", payload)
    print("\n" + json.dumps(scaling, indent=1))


if __name__ == "__main__":
    main()
