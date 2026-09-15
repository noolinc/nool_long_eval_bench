"""B10 part 1: self-replay — real admission cost on Nool's own repository.

Copies the Nool repo's working tree + `.nool` ledger (excluding `target/`,
`.git`, and other build/ephemeral state) into a scratch directory, then
replays the touched-path sets of the most recent real Synthesis/Mutation
knots as `propose --path <files> --json --fast` WITHOUT solidifying: each
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
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ENV, TempRoot, emit, run, run_split, summarize_ms, version_of  # noqa: E402

ORIGINAL_REPO = Path(
    os.environ.get("B10_SOURCE_REPO", "/Users/arunbalakrishnan/Development/NoolWorkspace/Nool")
)
REPLAY_COUNT = int(os.environ.get("B10_SELF_REPLAY_COUNT", "30"))
TIMEOUT_S = int(os.environ.get("B10_SELF_TIMEOUT_S", "60"))

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
EXCLUDE_NOOL_SUBDIRS = {"tmp", "try", "runs", "target", "session_transcript.jsonl", "incoming"}


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
                if sub.name in EXCLUDE_NOOL_SUBDIRS:
                    continue
                dst = nool_dest / sub.name
                if sub.is_dir():
                    shutil.copytree(sub, dst, symlinks=True)
                else:
                    shutil.copy2(sub, dst)
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
    (ws / ".gitignore").write_text(".nool/candidate.knot\n")
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


MUTATION_LINE = re.compile(r"^\s*-?\s*Mutation\s+(?:doc\s+|test\s+)?@\s+(\S+)")


def recent_touched_path_sets(repo: Path, n: int) -> list[list[str]]:
    """Parse `nool log --compact` for the last n Synthesis/Mutation entries'
    touched paths, filtered to files that actually exist in the snapshot."""
    code, out, _ = run(["nool", "log", "--compact"], repo, timeout=60)
    if code != 0:
        raise RuntimeError(f"nool log failed:\n{out}")
    sets: list[list[str]] = []
    current: list[str] = []
    for line in out.splitlines():
        m = MUTATION_LINE.match(line)
        if m:
            current.append(m.group(1))
            continue
        if current and (line.strip() == "" or re.match(r"^[0-9a-f]{8}\s+\[", line)):
            sets.append(current)
            current = []
            if len(sets) >= n:
                break
    if current and len(sets) < n:
        sets.append(current)
    existing_sets = []
    for paths in sets:
        keep = [p for p in paths if (repo / p).is_file()]
        if keep:
            existing_sets.append(keep)
    return existing_sets[:n]


COMMENT_BY_EXT = {
    ".rs": "// b10_self probe\n",
    ".go": "// b10_self probe\n",
    ".py": "# b10_self probe\n",
    ".ts": "// b10_self probe\n",
    ".toml": "# b10_self probe\n",
    ".md": "<!-- b10_self probe -->\n",
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


def measure_one(repo: Path, paths: list[str], idx: int) -> dict:
    touch(repo, paths)
    # --fast is NOT gate-only for a compiled/bundle file: propose_cmd.rs's
    # mode==Fast branch materializes a scratchpad and runs fast_validate
    # (cargo check-equivalent) unconditionally, never consulting
    # config.reification.enabled at all -- that flag is only checked in the
    # mode!=Fast branch. Confirmed this session (109s cold cargo check ate
    # the disk before this fix). --full + [reification] enabled=false is
    # the actual gate-only combination.
    cmd = ["nool", "propose", "--path", *paths, "--intent", f"b10-self replay {idx}",
           "--json", "--full", "--auto-justify"]
    t0 = time.monotonic()
    code, stdout, stderr, ms = run_split(cmd, repo, timeout=TIMEOUT_S)
    result = {
        "idx": idx, "n_paths": len(paths), "paths_sample": paths[:5],
        "exit_code": code, "wall_ms": round(ms, 2),
        "semantic_signal": None, "proposal_stages": None,
        "landed": False, "refused": code != 0, "dnf": False,
    }
    for line in stdout.splitlines():
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "semantic_signal" in obj:
            result["semantic_signal"] = obj["semantic_signal"]
        elif "proposal_stages" in obj:
            result["proposal_stages"] = obj["proposal_stages"]
    if code != 0 and os.environ.get("B10_SELF_DEBUG"):
        print(f"    -- refused, exit={code} --", file=sys.stderr)
        print("    STDOUT:", stdout[-2000:], file=sys.stderr)
        print("    STDERR:", stderr[-2000:], file=sys.stderr)
    run(["nool", "propose", "--abort"], repo, timeout=30)
    reset(repo, paths)
    return result


def summarize(results: list[dict]) -> dict:
    ok = [r for r in results if r["semantic_signal"] is not None]
    envelope_sizes = [r["semantic_signal"]["blast_radius"]["affected"] for r in ok]
    declared_sizes = [r["semantic_signal"]["blast_radius"]["declared"] for r in ok]
    statuses = [r["semantic_signal"]["blast_radius"]["status"] for r in ok]
    tiers = [r["semantic_signal"]["blast_radius"]["tier"] for r in ok]
    def plan_variant(plan):
        # A plan is either a bare variant name ("Precheck", "PackageTests",
        # ...) or, for the two variants that carry a reason, a single-key
        # dict ({"HumanApproval": "aram,auth"} / {"AttestationRequired": "..."})
        # -- normalize to just the variant name for counting.
        return next(iter(plan)) if isinstance(plan, dict) else plan

    plans = [plan_variant(r["semantic_signal"]["evidence_plan"]["plan"]) for r in ok]
    contracts_counts = [len(r["semantic_signal"]["envelope"]["contracts"]) for r in ok]
    wall = [r["wall_ms"] for r in results]
    ratio = [
        (r["semantic_signal"]["blast_radius"]["affected"] / r["n_paths"])
        for r in ok if r["n_paths"] > 0
    ]
    stage_ms: dict[str, list[float]] = {}
    for r in ok:
        stages = r.get("proposal_stages") or {}
        for k, v in (stages.get("ms") or {}).items():
            stage_ms.setdefault(k, []).append(v)

    def counts(items):
        out: dict[str, int] = {}
        for it in items:
            out[it] = out.get(it, 0) + 1
        return out

    return {
        "n_replayed": len(results),
        "n_measured": len(ok),
        "n_refused": sum(1 for r in results if r["refused"]),
        "wall_ms": summarize_ms(wall),
        "envelope_affected": summarize_ms(envelope_sizes) if envelope_sizes else None,
        "envelope_declared": summarize_ms(declared_sizes) if declared_sizes else None,
        "envelope_affected_over_declared_ratio": summarize_ms(ratio) if ratio else None,
        "envelope_status_counts": counts(statuses),
        "blast_tier_counts": counts(tiers),
        "evidence_plan_counts": counts(plans),
        "contracts_count": summarize_ms(contracts_counts) if contracts_counts else None,
        "stage_ms": {k: summarize_ms(v) for k, v in stage_ms.items()},
    }


def main():
    nool_bin = shutil.which("nool")
    if not nool_bin:
        print("ERROR: nool not on PATH", file=sys.stderr)
        sys.exit(1)
    print(f"[b10_self] nool binary: {nool_bin}")
    print(f"[b10_self] nool version: {version_of(['nool', 'version', '--json'])[:200]}")
    print(f"[b10_self] source repo: {ORIGINAL_REPO}")

    with TempRoot("b10self") as tmp:
        ws = tmp / "repo"
        print(f"[b10_self] copying snapshot into {ws} (excluding target/, .git — this repo is large)...")
        t0 = time.monotonic()
        copy_repo_snapshot(ws)
        copy_s = time.monotonic() - t0
        print(f"[b10_self] copy done in {copy_s:.1f}s")
        reinit_lightweight_git(ws)
        disable_reification(ws)

        print(f"[b10_self] parsing the last {REPLAY_COUNT} touched-path sets from nool log...")
        path_sets = recent_touched_path_sets(ws, REPLAY_COUNT)
        print(f"[b10_self] got {len(path_sets)} usable sets (existing files, non-empty)")
        if not path_sets:
            print("ERROR: no usable touched-path sets found", file=sys.stderr)
            sys.exit(1)

        results = []
        for i, paths in enumerate(path_sets):
            try:
                r = measure_one(ws, paths, i)
            except subprocess.TimeoutExpired:
                r = {
                    "idx": i, "n_paths": len(paths), "paths_sample": paths[:5],
                    "exit_code": None, "wall_ms": None,
                    "semantic_signal": None, "proposal_stages": None,
                    "landed": False, "refused": False, "dnf": True,
                }
                run(["nool", "propose", "--abort"], ws, timeout=30)
                reset(ws, paths)
            results.append(r)
            sig = r.get("semantic_signal")
            aff = sig["blast_radius"]["affected"] if sig else "N/A"
            plan = sig["evidence_plan"]["plan"] if sig else "N/A"
            print(f"  [{i:3d}] {len(paths):3d} paths -> affected={aff} plan={plan} "
                  f"wall={r['wall_ms']}ms exit={r['exit_code']}")

        summary = summarize(results)
        payload = {
            "config": {
                "source_repo": str(ORIGINAL_REPO),
                "replay_count_requested": REPLAY_COUNT,
                "timeout_s": TIMEOUT_S,
                "copy_seconds": round(copy_s, 1),
            },
            "results": results,
            "summary": summary,
        }
        emit("b10_self", payload)
        print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
