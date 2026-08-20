"""B1 — Happy-path overhead tax (H6).

(a) Latency of nool's per-tool-call agent hook, invoked directly with a
    recorded PostToolUse-style payload, per harness hook installed by
    `nool init` (claude, codex, gemini, opencode, pi).
(b) `nool propose --fast --solidify` vs `git add -A && git commit` on matched
    change sets of 1, 10, and 100 files.

Reports medians over repeated runs. Numbers only; no interpretation.
"""

import json

from common import (TempRoot, emit, git_commit_all, make_workspace, nool_land,
                    run, summarize_ms)

HOOK_REPS = 20
COMMIT_REPS = {1: 10, 10: 10, 100: 5}

HOOK_PAYLOAD = json.dumps({
    "hook_event_name": "PostToolUse",
    "tool_name": "Edit",
    "tool_input": {"file_path": "src/lib.go"},
    "tool_response": {"success": True},
    "session_id": "bench-b1",
})


def bench_hooks_with_stdin(root):
    """Hook latency with a realistic event payload piped to stdin."""
    import subprocess
    import time as _t
    from common import ENV
    ws = make_workspace(root, "hooks_stdin", nool=True)
    (ws / "src").mkdir()
    (ws / "src" / "lib.go").write_text("package lib\n")
    results = {}
    hooks_dir = ws / ".nool" / "hooks" / "agent"
    for hook in sorted(hooks_dir.glob("*_hook.sh")):
        samples, codes = [], set()
        for _ in range(HOOK_REPS):
            t0 = _t.monotonic()
            p = subprocess.run(["bash", str(hook)], cwd=str(ws), env=ENV,
                               input=HOOK_PAYLOAD, text=True, timeout=60,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            samples.append((_t.monotonic() - t0) * 1000.0)
            codes.add(p.returncode)
        results[hook.stem] = {**summarize_ms(samples), "exit_codes_seen": sorted(codes)}
    return results


def write_change(ws, n_files, rep):
    for i in range(n_files):
        (ws / f"file_{i:03d}.go").write_text(
            f"package bench\n\n// rep {rep}\nfunc F{i}_{rep}() int {{ return {rep} }}\n")


def bench_commit_paths(root):
    out = {}
    for n_files, reps in COMMIT_REPS.items():
        git_ws = make_workspace(root, f"git_{n_files}")
        nool_ws = make_workspace(root, f"nool_{n_files}", nool=True)
        git_ms, nool_ms, nool_fail = [], [], 0
        for rep in range(reps):
            write_change(git_ws, n_files, rep)
            _, _, ms = git_commit_all(git_ws, f"rep {rep}")
            git_ms.append(ms)
            write_change(nool_ws, n_files, rep)
            # ≥~100 nodes trips nool's blast-radius gate in non-interactive
            # mode; --auto-justify is the sanctioned wide-change path, so the
            # 100-file cell measures that path (recorded in the cell).
            extra = ["--auto-justify"] if n_files >= 100 else None
            code, _, ms = nool_land(nool_ws, f"rep {rep}", extra=extra)
            nool_ms.append(ms)
            if code != 0:
                nool_fail += 1
        out[f"{n_files}_files"] = {
            "git_add_commit": summarize_ms(git_ms),
            "nool_propose_fast_solidify": summarize_ms(nool_ms),
            "nool_auto_justify_used": n_files >= 100,
            "nool_nonzero_exits": nool_fail,
        }
    return out


def main():
    with TempRoot("b1") as root:
        hooks = bench_hooks_with_stdin(root)
        commits = bench_commit_paths(root)
    emit("b1_overhead", {
        "config": {"hook_reps": HOOK_REPS, "commit_reps": COMMIT_REPS},
        "hook_latency_with_payload": hooks,
        "landing_a_change": commits,
    })


if __name__ == "__main__":
    main()
