#!/usr/bin/env python3
"""Track D — Fleet Operations Benchmark (pre-registered in the design spec §8a).

N real agents process a ticket backlog against one shared codebase.

  git_fleet : uncoordinated baseline — every ticket dispatched in parallel;
              integration is a sequential `git merge` queue in ticket order.
  nool_fleet: coordinated — tickets registered as nool tasks; dispatch is
              GATED by `nool announce intent` + `nool discover conflicts`
              over each ticket's declared footprint (held while a
              conflicting ticket is in flight); integration is
              `nool merge` on completion.

Identical prompts, model, worker count, and worktree isolation in both arms.
Main-branch health (build + smoke tests) is recorded after every merge;
ticket acceptance is scored against hidden per-ticket tests at the end.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters import claude as claude_adapter  # noqa: E402
from run_experiment import ENV, RESULTS, TRANSCRIPTS, sh  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TASK = REPO / "tasks" / "fleet_service"

PROMPT = """You are working in a Go service repository (module bench/fleetsvc).
Implement the following ticket. Modify only what the ticket requires.

Ticket {tid} — {title}

{spec}

Verify with `go build ./...` and `go test ./...` (the existing tests must
stay green). Land your work with the version-control workflow available in
this repository, then stop.
"""


def setup_ws(arm, parent):
    ws = Path(parent) / "main_ws"
    shutil.copytree(TASK / "starter", ws)
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "bench@nool-benchmarks.local"],
                ["git", "config", "user.name", "Bench"],
                ["git", "add", "-A"], ["git", "commit", "-qm", "base service"]):
        sh(cmd, ws, check=True)
    if arm == "nool_fleet":
        code, out = sh(["nool", "init"], ws, timeout=120)
        if code != 0:
            raise RuntimeError(out)
    return ws


def health(ws):
    b, _ = sh(["go", "build", "./..."], ws, timeout=120)
    t, _ = sh(["go", "test", "./..."], ws, timeout=180)
    return {"build_ok": b == 0, "smoke_ok": t == 0}


def agent_ticket(ws, parent, ticket, model, run_id):
    wt = Path(parent) / f"wt_{ticket['id']}"
    sh(["git", "worktree", "add", "-q", "-b", f"ticket_{ticket['id']}",
        str(wt), "main"], ws, check=True)
    prompt = PROMPT.format(tid=ticket["id"], title=ticket["title"],
                           spec=ticket["spec"])
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    tpath = TRANSCRIPTS / f"{run_id}_{ticket['id']}.jsonl"
    res = claude_adapter.run(wt, prompt, model, max_turns=30, timeout_s=600,
                             transcript_path=tpath, env=ENV)
    sh(["git", "add", "-A"], wt)
    sh(["git", "commit", "-qm", f"{ticket['id']} leftovers"], wt)
    return {**res, "transcript": str(tpath.relative_to(REPO))}


def integrate(ws, arm, ticket):
    branch = f"ticket_{ticket['id']}"
    if arm == "nool_fleet":
        code, out = sh(["nool", "merge", branch, "--compact"], ws, timeout=300)
    else:
        code, out = sh(["git", "merge", "-q", "--no-edit", branch], ws, timeout=300)
    _, status = sh(["git", "status", "--porcelain"], ws)
    conflicted = any(l[:2] in ("UU", "AA", "DD", "AU", "UA", "DU", "UD")
                     for l in status.splitlines())
    if conflicted:
        sh(["git", "merge", "--abort"], ws)
    return {"ticket": ticket["id"], "clean": not conflicted, "exit_code": code,
            "post_merge_health": health(ws) if not conflicted else None}


def score(ws, tickets):
    out = {}
    for t in tickets:
        dst = ws / "accept" / t["id"]
        shutil.copytree(TASK / "accept" / t["id"], dst)
        code, _ = sh(["go", "test", f"./accept/{t['id']}/"], ws, timeout=120)
        out[t["id"]] = code == 0
        shutil.rmtree(ws / "accept")
    return out


def nool_gate(ws, ticket):
    """Announce this ticket's footprint; report nool's conflict verdict."""
    fp = ",".join(ticket["footprint"])
    a_code, a_out = sh(["nool", "announce", "intent", "--intent",
                        f"ticket {ticket['id']}: {ticket['title']}",
                        "--target-nodes", fp, "--compact"], ws, timeout=120)
    d_code, d_out = sh(["nool", "discover", "conflicts",
                        *ticket["footprint"], "--compact"], ws, timeout=120)
    return {"announce_exit": a_code, "discover_exit": d_code,
            "discover_tail": d_out.strip().splitlines()[-2:]}


def run_fleet(arm, model, n_workers):
    run_id = f"fleet_{arm}_{uuid.uuid4().hex[:8]}"
    tickets = json.loads((TASK / "tickets.json").read_text())["tickets"]
    parent = tempfile.mkdtemp(prefix=run_id + "_")
    ws = setup_ws(arm, parent)
    rec = {"run_id": run_id, "arm": arm, "model": model, "n_workers": n_workers,
           "started_utc": datetime.now(timezone.utc).isoformat(),
           "preflight": claude_adapter.preflight(),
           "agents": {}, "integration": [], "gating": {}}
    t0 = time.monotonic()

    if arm == "git_fleet":
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=n_workers) as ex:
            futs = {ex.submit(agent_ticket, ws, parent, t, model, run_id): t
                    for t in tickets}
            for f in futs:
                rec["agents"][futs[f]["id"]] = f.result()
        for t in tickets:  # sequential merge queue, ticket order
            rec["integration"].append(integrate(ws, arm, t))
    else:
        lock = threading.Lock()
        inflight = {}          # ticket id -> footprint set
        done = set()
        results = {}

        def worker(t):
            res = agent_ticket(ws, parent, t, model, run_id)
            with lock:
                rec["agents"][t["id"]] = res
                rec["integration"].append(integrate(ws, arm, t))
                del inflight[t["id"]]
                done.add(t["id"])

        threads = []
        pending = list(tickets)
        while pending or inflight:
            with lock:
                busy = set().union(*inflight.values()) if inflight else set()
                ready = []
                for t in pending:
                    if set(t["footprint"]) & busy:
                        continue
                    if len(inflight) + len(ready) >= n_workers:
                        break
                    ready.append(t)
                for t in ready:
                    rec["gating"].setdefault(t["id"], []).append(nool_gate(ws, t))
                    inflight[t["id"]] = set(t["footprint"])
                    pending.remove(t)
                    th = threading.Thread(target=worker, args=(t,))
                    th.start()
                    threads.append(th)
            time.sleep(2)
        for th in threads:
            th.join()

    rec["wall_ms"] = round((time.monotonic() - t0) * 1000.0, 1)
    rec["acceptance"] = score(ws, tickets)
    rec["final_health"] = health(ws)
    _, glog = sh(["git", "log", "--oneline"], ws)
    rec["git_commits_on_main"] = len(glog.splitlines())
    if arm == "nool_fleet":
        code, nlog = sh(["nool", "log", "--json"], ws)
        try:
            rec["nool_knots"] = len(json.loads(nlog))
        except Exception:
            rec["nool_knots"] = None
    rec["cost_usd"] = round(sum((a.get("cost_usd") or 0)
                                for a in rec["agents"].values()), 4)
    rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
    shutil.rmtree(parent, ignore_errors=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "fleet_runs.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    passed = sum(1 for v in rec["acceptance"].values() if v)
    print(f"[{run_id}] accepted {passed}/{len(tickets)} "
          f"wall={rec['wall_ms']/1000:.0f}s cost=${rec['cost_usd']}", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--arms", default="git_fleet,nool_fleet")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()
    for arm in args.arms.split(","):
        run_fleet(arm, args.model, args.workers)


if __name__ == "__main__":
    main()
