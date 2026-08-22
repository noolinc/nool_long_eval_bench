#!/usr/bin/env python3
"""Track C experiment runner — 2x2 (VCS: git|nool x mode: single|multi).

Per run: fresh workspace from the task's starter, agent(s) driven headlessly
via the harness adapter with the SAME pinned model in every cell, hidden
tests copied in only at scoring time, one JSONL record appended to
results/trackc/runs.jsonl (transcripts stored separately, gitignored).

Multi-agent protocol (identical decomposition across arms): each sub-agent
works in an isolated git worktree on its own branch and commits with git —
worktrees are deliberately outside nool tracking in both arms, so the arms
differ ONLY at integration: `git merge` vs `nool merge`, applied in fixed
order with no conflict resolution. Single-agent cells exercise the full
in-workspace workflow difference (nool hooks + propose/solidify vs git).
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters import claude as claude_adapter  # noqa: E402
from adapters import opencode as opencode_adapter  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TASKS = REPO / "tasks"
RESULTS = REPO / "results" / "trackc"
TRANSCRIPTS = RESULTS / "transcripts"

ADAPTERS = {"claude": claude_adapter, "opencode": opencode_adapter}
CELLS = ["single_git", "single_nool", "multi_git", "multi_nool"]

ENV = dict(os.environ, NOOL_NO_DAEMON="1", GIT_TERMINAL_PROMPT="0")


def sh(cmd, cwd, timeout=300, check=False):
    p = subprocess.run(cmd, cwd=str(cwd), env=ENV, timeout=timeout, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd} -> {p.returncode}\n{p.stdout}")
    return p.returncode, p.stdout


def load_task(task_id):
    tdir = TASKS / task_id
    cfg = {}
    for line in (tdir / "task.yaml").read_text().splitlines():
        line = line.split("#")[0].rstrip()
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            cfg[k.strip()] = v.strip()
    spec_hash = hashlib.sha256()
    for f in sorted(tdir.rglob("*.md")):
        spec_hash.update(f.read_bytes())
    return {
        "dir": tdir,
        "id": task_id,
        "k": int(cfg.get("multi_agent_k", 2)),
        "agent_timeout_s": 900,
        "spec_hash": spec_hash.hexdigest()[:16],
    }


def setup_workspace(task, arm, parent):
    ws = Path(parent) / "ws"
    shutil.copytree(task["dir"] / "starter", ws)
    sh(["git", "init", "-q", "-b", "main"], ws, check=True)
    sh(["git", "config", "user.email", "bench@nool-benchmarks.local"], ws, check=True)
    sh(["git", "config", "user.name", "Bench"], ws, check=True)
    sh(["git", "add", "-A"], ws, check=True)
    sh(["git", "commit", "-qm", "task starter"], ws, check=True)
    if arm == "nool":
        code, out = sh(["nool", "init"], ws, timeout=120)
        if code != 0:
            raise RuntimeError(f"nool init failed:\n{out}")
    return ws


def agent_run(adapter, ws, prompt, model, task, run_id, label):
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    tpath = TRANSCRIPTS / f"{run_id}_{label}.jsonl"
    return adapter.run(ws, prompt, model, max_turns=40,
                       timeout_s=task["agent_timeout_s"],
                       transcript_path=tpath, env=ENV), str(tpath.relative_to(REPO))


def integrate(ws, arm, k):
    """Merge agent branches in fixed order; conflict -> record + abort."""
    outcomes = []
    for i in range(1, k + 1):
        if arm == "nool":
            code, out = sh(["nool", "merge", f"agent_{i}", "--compact"], ws, timeout=300)
        else:
            code, out = sh(["git", "merge", "-q", "--no-edit", f"agent_{i}"], ws, timeout=300)
        _, status = sh(["git", "status", "--porcelain"], ws)
        conflicted = any(l[:2] in ("UU", "AA", "DD", "AU", "UA", "DU", "UD")
                         for l in status.splitlines())
        if conflicted:
            sh(["git", "merge", "--abort"], ws)
        outcomes.append({"branch": f"agent_{i}", "clean": not conflicted,
                         "exit_code": code})
    return outcomes


def score(task, ws):
    for t in (task["dir"] / "hidden_tests").glob("*"):
        shutil.copy(t, ws / t.name)
    b_code, b_out = sh(["go", "build", "./..."], ws, timeout=120)
    t_code, t_out = sh(["go", "test", "./..."], ws, timeout=120)
    for t in (task["dir"] / "hidden_tests").glob("*"):
        (ws / t.name).unlink(missing_ok=True)
    return {
        "build_ok": b_code == 0,
        "tests_ok": t_code == 0,
        "build_tail": b_out.strip().splitlines()[-3:],
        "test_tail": t_out.strip().splitlines()[-5:],
    }


def one_run(task, cell, rep, model, harness):
    adapter = ADAPTERS[harness]
    mode, arm = cell.split("_")
    run_id = f"{task['id']}_{cell}_r{rep}_{uuid.uuid4().hex[:8]}"
    rec = {
        "run_id": run_id, "task": task["id"], "cell": cell, "rep": rep,
        "harness": harness, "model_requested": model,
        "spec_hash": task["spec_hash"],
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "preflight": adapter.preflight(),
        "nool_version": subprocess.run(["nool", "--version"], capture_output=True,
                                       text=True).stdout.strip(),
    }
    parent = tempfile.mkdtemp(prefix=f"trackc_{run_id}_")
    try:
        ws = setup_workspace(task, arm, parent)
        if mode == "single":
            prompt = (task["dir"] / "spec.md").read_text()
            res, tpath = agent_run(adapter, ws, prompt, model, task, run_id, "solo")
            rec["agent"] = {**res, "transcript": tpath}
        else:
            agents = []
            for i in range(1, task["k"] + 1):
                wt = Path(parent) / f"agent_{i}"
                sh(["git", "worktree", "add", "-q", "-b", f"agent_{i}", str(wt), "main"],
                   ws, check=True)
                prompt = (task["dir"] / "spec_parts" / f"{i}.md").read_text()
                res, tpath = agent_run(adapter, wt, prompt, model, task, run_id, f"a{i}")
                # Land uncommitted leftovers so the branch reflects the work.
                sh(["git", "add", "-A"], wt)
                sh(["git", "commit", "-qm", f"agent {i} leftovers"], wt)
                agents.append({**res, "transcript": tpath, "part": i})
            rec["agents"] = agents
            rec["integration"] = integrate(ws, arm, task["k"])
        rec["score"] = score(task, ws)
        rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        rec["fatal_error"] = repr(e)
    finally:
        shutil.rmtree(parent, ignore_errors=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "runs.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    ok = rec.get("score", {}).get("tests_ok")
    print(f"[{run_id}] tests_ok={ok}", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", default="claude", choices=list(ADAPTERS))
    ap.add_argument("--model", required=True,
                    help="pinned model id used for EVERY cell")
    ap.add_argument("--tasks", default="redux_go")
    ap.add_argument("--cells", default="all")
    ap.add_argument("--reps", type=int, default=1)
    args = ap.parse_args()

    cells = CELLS if args.cells == "all" else args.cells.split(",")
    for task_id in args.tasks.split(","):
        task = load_task(task_id)
        for rep in range(args.reps):
            for cell in cells:
                one_run(task, cell, rep, args.model, args.harness)


if __name__ == "__main__":
    main()
