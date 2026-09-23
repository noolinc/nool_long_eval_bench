"""B10 part 1: self-replay — real admission cost on Nool's own repository.

Copies the Nool repo's working tree + `.nool` ledger (excluding `target/`,
`.git`, and other build/ephemeral state) into a scratch directory, then
replays the touched-path sets of the most recent real Synthesis/Mutation
knots as `propose --path <files> --json --full` with `[reification]
enabled = false` (the admission-only combination) WITHOUT solidifying: each
measurement appends a trivial one-line comment to every file in the set (a
real, syntactically-safe diff), proposes, captures the two JSON lines nool
prints (`semantic_signal`, `proposal_stages`), then `propose --abort` +
`git checkout --` to discard and reset before the next replay.

This produces the real distribution of envelope size, envelope status,
evidence-plan tier, contracts count, and per-stage wall time on a genuine
~860-file, 1,200+-knot production repository — the thing a synthetic fixture
can only approximate. No LLM involvement.

Requires: the `nool` CLI on PATH (point PATH at a specific debug build to
pin what's measured), git, python3.11+. Read-only against the ORIGINAL repo
(only ever writes into the scratch copy).
"""

import json
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from common import emit, run, summarize_ms  # noqa: E402
import b10_assurance_scaling as b10  # noqa: E402  (frozen binary, outcome + selection classifiers)

ORIGINAL_REPO = Path(
    os.environ.get("B10_SOURCE_REPO", "/Users/arunbalakrishnan/Development/NoolWorkspace/Nool")
)
REPLAY_COUNT = int(os.environ.get("B10_SELF_REPLAY_COUNT", "40"))
MIN_REPLAYS = 30  # acceptance floor (task 3de0ac0d)
LOG_LIMIT = int(os.environ.get("B10_SELF_LOG_LIMIT", "1500"))
TIMEOUT_S = int(os.environ.get("B10_SELF_TIMEOUT_S", "120"))
TMP_ROOT = Path(os.environ.get("B10_SELF_TMP", "/tmp/noolbench_b10self"))

# Never copy these: target/ is tens of GB of build artifacts, .git is history
# we don't need (a fresh single-commit init gives git-diff-based change
# detection everything it needs), and these .nool subdirs are ephemeral
# scratch/run state, not the ledger itself.
EXCLUDE_DIRS = {
    "target", ".git", "node_modules", "dist", ".nool-tmp",
    # 6.8GB of pre-built release tarballs (nool-hub/releases) matched by a
    # git-lfs `clean` filter; `git add -A` on a fresh init tries to smudge
    # them into a local LFS object cache and runs the scratch disk out of
    # space (confirmed this session) — irrelevant to a code-change
    # benchmark, so they're never copied in the first place.
    "releases",
}
# `.nool/target` is the reification CARGO_TARGET_DIR (can be several GB —
# confirmed 6GB on the source repo this session; safe to skip, it rebuilds
# on demand). `session_transcript.jsonl` and `incoming` are this session's
# own agent-transcript/spool state, irrelevant to what's being measured.
EXCLUDE_NOOL_SUBDIRS = {"tmp", "try", "runs", "target", "session_transcript.jsonl", "incoming",
                        "code", "locks"}  # live `nool code` sessions (sockets) and lock files


def copy_repo_snapshot(dest: Path) -> None:
    """Copy the working tree + `.nool` ledger into `dest`, skipping build/ephemeral state."""
    dest.mkdir(parents=True, exist_ok=True)
    for entry in ORIGINAL_REPO.iterdir():
        name = entry.name
        if name in EXCLUDE_DIRS:
            continue
        if name == ".nool":
            nool_dest = dest / ".nool"
            nool_dest.mkdir(exist_ok=True)
            for sub in entry.iterdir():
                if sub.name in EXCLUDE_NOOL_SUBDIRS or sub.name.startswith("nool.db-"):
                    continue  # -wal/-shm/-journal: folded in by the backup below
                dst = nool_dest / sub.name
                try:
                    if sub.name == "nool.db":
                        # The source ledger is live (other agents write it):
                        # a file copy can tear it or race its WAL away. The
                        # SQLite online backup is one consistent snapshot.
                        src = sqlite3.connect(f"file:{sub}?mode=ro", uri=True)
                        out = sqlite3.connect(str(dst))
                        with out:
                            src.backup(out)
                        out.close()
                        src.close()
                    elif sub.is_dir():
                        shutil.copytree(sub, dst, symlinks=True, ignore_dangling_symlinks=True,
                                        ignore=shutil.ignore_patterns("*.sock", "*.lock"))
                    else:
                        shutil.copy2(sub, dst)
                except FileNotFoundError:
                    continue  # vanished mid-copy (lock/temp file of a live writer)
            continue
        dst = dest / name
        if entry.is_dir():
            shutil.copytree(entry, dst, symlinks=True, ignore=shutil.ignore_patterns(*EXCLUDE_DIRS))
        else:
            shutil.copy2(entry, dst)


def reinit_lightweight_git(ws: Path) -> None:
    """A single-commit git history is enough for nool's git-diff change
    detection; the real 1.8GB .git isn't needed and isn't copied."""
    run(["git", "init", "-q", "-b", "main"], ws, check=True)
    run(["git", "config", "user.email", "b10-self@nool-benchmarks.local"], ws, check=True)
    run(["git", "config", "user.name", "B10Self"], ws, check=True)
    gi = ws / ".gitignore"
    # Append, never replace: the copied repo's own ignore rules decide what
    # counts as a tracked file (the R reported for region_over_R).
    gi.write_text((gi.read_text() if gi.exists() else "") + "\n.nool/\n")
    run(["git", "add", "-A"], ws, check=True)
    code, out, _ = run(["git", "commit", "-qm", "b10_self snapshot"], ws)
    if code != 0:
        raise RuntimeError(f"initial commit failed:\n{out}")


def disable_reification(ws: Path) -> None:
    """b10_self measures admission/routing cost (envelope, contracts,
    evidence plan), not compilation. The source repo's real nool.toml has
    `[reification] enabled = true`, so `--fast` on a .rs bundle still runs a
    real `cargo check` against a cold, uncached scratch target dir on every
    replay -- confirmed this session to make even a handful of replays take
    minutes. Turn it off in the SCRATCH copy only (never the source repo);
    this is the "gate_only" cell from the original B10 design."""
    path = ws / "nool.toml"
    if not path.exists():
        return
    text = path.read_text()
    text = re.sub(r"(\[reification\]\nenabled = )true", r"\1false", text, count=1)
    path.write_text(text)


ENTRY_LINE = re.compile(r"^([0-9a-f]{8}) \[[^\]]+\]\s+(\S+)")
MUTATION_PATH = re.compile(r"Mutation\s+(?:[a-z]+\s+)?@\s+(\S+)")


def parse_mutation_knots(log_text: str) -> list[dict]:
    """Split `nool log --compact` into entries and keep Mutation/Synthesis
    knots with their touched paths (Task/Bug/attestation entries dropped)."""
    knots, cur = [], None
    for line in log_text.splitlines():
        m = ENTRY_LINE.match(line)
        if m:
            if cur and cur["paths"]:
                knots.append(cur)
            kind = m.group(2)
            cur = {"knot": m.group(1), "kind": kind, "paths": []} \
                if kind in ("Mutation", "Synthesis") else None
        if cur is not None:
            cur["paths"] += [p for p in MUTATION_PATH.findall(line) if p not in cur["paths"]]
    if cur and cur["paths"]:
        knots.append(cur)
    return knots


def recent_touched_path_sets(repo: Path, n: int) -> list[dict]:
    """The last n mutation knots whose touched files all still exist."""
    code, out, _ = run(["nool", "log", "--compact", "--limit", str(LOG_LIMIT)], repo, timeout=300)
    if code != 0:
        raise RuntimeError(f"nool log failed:\n{out[-2000:]}")
    usable = []
    for k in parse_mutation_knots(out):
        keep = [p for p in k["paths"] if (repo / p).is_file()]
        if keep:
            usable.append({**k, "paths": keep, "paths_dropped": len(k["paths"]) - len(keep)})
        if len(usable) >= n:
            break
    return usable


def repository_size(repo: Path) -> dict:
    code, out, _ = run(["git", "ls-files"], repo, timeout=120)
    files = [f for f in out.splitlines() if f and not f.startswith(".nool/")] if code == 0 else []
    return {"tracked_files": len(files)}


COMMENT_BY_EXT = {
    ".rs": "// b10_self probe\n",
    ".go": "// b10_self probe\n",
    ".py": "# b10_self probe\n",
    ".ts": "// b10_self probe\n",
    ".toml": "# b10_self probe\n",
    ".md": "<!-- b10_self probe -->\n",
    # formats with no comment syntax: a trailing newline is a real, valid diff
    ".json": "\n", ".jsonl": "\n", ".lock": "\n", ".snap": "\n",
}


def probe_comment_for(path: str) -> str:
    return COMMENT_BY_EXT.get(Path(path).suffix, "// b10_self probe\n")


def touch(repo: Path, paths: list[str]) -> None:
    for p in paths:
        f = repo / p
        with f.open("a") as fh:
            fh.write(probe_comment_for(p))


def reset(repo: Path, paths: list[str]) -> None:
    run(["git", "checkout", "--", *paths], repo, check=True)


def measure_one(repo: Path, knot: dict, idx: int, r_files: int) -> dict:
    """Replay one knot's touched-path set as an admission-only propose
    (--full --json, reification off), plus the affected-tests selection."""
    paths = knot["paths"]
    touch(repo, paths)
    try:
        adm = b10.propose_json(repo, paths, f"b10-self replay {idx} ({knot['knot']})")
    finally:
        b10.abort_candidates(repo)
        reset(repo, paths)
    t = b10.timed(["nool", "query", "affected-tests", "--paths", ",".join(paths), "--format", "json"], repo)
    sel = None
    if t["code"] == 0 and "{" in t["stdout"]:
        try:
            sel = json.loads(t["stdout"][t["stdout"].find("{"):])
        except json.JSONDecodeError:
            sel = None
    if sel is None:
        selection = "unparsed" if not t["timed_out"] else "dnf"
    elif sel.get("mode") == "full" or sel.get("run_all"):
        selection = "full_fallback"
    elif not sel.get("tests"):
        selection = "empty"  # no test can see the change: never an O(change) win
    else:
        selection = "selected"
    region = adm["envelope"]
    return {
        "idx": idx, "knot": knot["knot"], "knot_kind": knot["kind"],
        "n_paths": len(paths), "paths_sample": paths[:5],
        "outcome": adm["outcome"], "exit_code": adm["exit_code"], "wall_ms": adm["wall_ms"],
        # exit 3 here is usually a lease copied from the live source ledger
        # (another agent is working on those files right now), not a gate verdict
        "refusal_reason": adm["stderr_tail"] or None,
        "region_size": region, "region_over_R": round(region / r_files, 5) if region is not None else None,
        "envelope_status": adm["envelope_status"], "contracts_count": adm["contracts_count"],
        "plan": adm["plan"], "stages": adm["stages"],
        "selection_mode": selection, "selection_reason": (sel or {}).get("reason"),
        "tests_selected": len((sel or {}).get("tests") or []),
        "selection_wall_ms": t["wall_ms"],
    }


def summarize(results: list[dict], r_files: int) -> dict:
    ok = [r for r in results if r["outcome"] == "landed"]

    def counts(items):
        out: dict[str, int] = {}
        for it in items:
            out[str(it)] = out.get(str(it), 0) + 1
        return out

    stage_ms: dict[str, list[float]] = {}
    for r in ok:
        for k, v in ((r.get("stages") or {}).get("ms") or {}).items():
            stage_ms.setdefault(k, []).append(v)
    sel = [r["selection_mode"] for r in results]
    region = [r["region_size"] for r in ok if r["region_size"] is not None]
    frac = [r["region_over_R"] for r in ok if r["region_over_R"] is not None]
    return {
        "n_replayed": len(results),
        "meets_min_replays": len(results) >= MIN_REPLAYS,
        "repository_tracked_files": r_files,
        "counts": b10.outcome_counts(results),
        "wall_ms": b10.timing(results),
        # summarize_ms's *_ms keys are plain order statistics here (counts, fractions)
        "region_size": summarize_ms(region),
        "region_over_R": summarize_ms(frac),
        "region_over_R_values": sorted(frac),
        "envelope_status_counts": counts(r["envelope_status"] for r in ok),
        "evidence_plan_counts": counts(r["plan"] for r in ok),
        "contracts_count": summarize_ms([r["contracts_count"] for r in ok if r["contracts_count"] is not None]),
        "selection_mode_counts": counts(sel),
        "full_suite_fallback_rate": round(sel.count("full_fallback") / len(sel), 3) if sel else None,
        "empty_selection_rate": round(sel.count("empty") / len(sel), 3) if sel else None,
        "stage_ms": {k: summarize_ms(v) for k, v in sorted(stage_ms.items())},
    }


def main():
    if os.environ.get("B10_RESULTS_DIR"):  # sanity runs never overwrite committed results
        common.RESULTS_DIR = Path(os.environ["B10_RESULTS_DIR"]).resolve()
    b10.use_frozen_binary()
    b10.check_temp_root(TMP_ROOT)
    gate_start = b10.binary_identity(b10.FROZEN_BIN)
    if not b10.binary_gate(gate_start, gate_start)["valid"] and not os.environ.get("B10_ALLOW_UNFROZEN"):
        raise SystemExit(f"b10_self: refusing unfrozen binary {gate_start}")
    print(f"[b10_self] nool: {b10.FROZEN_BIN} {gate_start['build'].get('version')} "
          f"sha256={gate_start['sha256'][:16]}")
    print(f"[b10_self] source repo: {ORIGINAL_REPO}")

    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    try:
        ws = TMP_ROOT / "repo"
        print(f"[b10_self] copying snapshot into {ws} (excluding target/, .git) ...")
        t0 = time.monotonic()
        copy_repo_snapshot(ws)
        copy_s = time.monotonic() - t0
        reinit_lightweight_git(ws)
        disable_reification(ws)
        size = repository_size(ws)
        print(f"[b10_self] copy {copy_s:.1f}s, {size['tracked_files']} tracked files")

        knots = recent_touched_path_sets(ws, REPLAY_COUNT)
        print(f"[b10_self] {len(knots)} usable mutation knots (requested {REPLAY_COUNT})")
        if len(knots) < MIN_REPLAYS:
            raise SystemExit(f"b10_self: only {len(knots)} usable mutation knots (< {MIN_REPLAYS})")

        results = []
        for i, k in enumerate(knots):
            r = measure_one(ws, k, i, size["tracked_files"])
            results.append(r)
            print(f"  [{i:3d}] {k['knot']} {r['n_paths']:3d} paths -> region={r['region_size']} "
                  f"({r['region_over_R']}) status={r['envelope_status']} plan={r['plan']} "
                  f"sel={r['selection_mode']} wall={r['wall_ms']}ms {r['outcome']}")
    finally:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    gate = b10.binary_gate(gate_start, b10.binary_identity(b10.FROZEN_BIN))
    summary = summarize(results, size["tracked_files"])
    payload = {
        "part": "b10_self",
        "config": {
            "source_repo": str(ORIGINAL_REPO),
            "replay_count_requested": REPLAY_COUNT, "log_limit": LOG_LIMIT,
            "timeout_s": TIMEOUT_S, "copy_seconds": round(copy_s, 1),
            "temp_root": str(TMP_ROOT),
            "admission_mode": "--full --json --auto-justify, [reification] enabled=false, not solidified",
        },
        "binary_gate": gate,
        "valid": gate["valid"],
        "results": results,
        "summary": summary,
    }
    emit("b10_self", payload)
    print(json.dumps({k: summary[k] for k in ("n_replayed", "counts", "region_over_R",
                                             "full_suite_fallback_rate", "envelope_status_counts")},
                     indent=1))
    if not gate["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
