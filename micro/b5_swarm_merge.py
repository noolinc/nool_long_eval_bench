"""B5 — Swarm merge (H2). Hardened successor to archive/run_swarm_benchmark.sh.

N agent branches diverge from one base and are merged back sequentially.

Scenarios:
  disjoint       : each agent adds its own file (negative control — both arms
                   must merge all N cleanly)
  same_anchor    : every agent inserts at the same anchor line (worst case —
                   textual merging cannot help; expected to conflict in both)
  diff_functions : each agent appends its own new method to the same file
                   (the AST-mergeable case where a semantic merge could
                   differ from git's textual merge)

A merge SUCCEEDS only when four independent observations agree: the
command exited 0, the working tree holds no conflict markers or unmerged
paths, HEAD advanced, and the branch's own change is present in the merged
tree. The 2026-09-13 audit showed the earlier criterion (`not
tree_conflicted` alone) reporting 15/15 clean merges with every merge
command mocked to fail and the tree untouched: a refused merge, a silent
no-op and a partial landing all leave a clean tree. Each observation is
recorded per branch so the scorer can be checked against injected
failures (`validate_scorers.py`). `tree_clean` is kept as the historical
file-level metric; `success` is what counts. After the last merge the
cumulative symbol inventory and a `go vet` of the merged tree are recorded,
so a merge that landed text but broke the package is visible.
For the nool arm the semantic layer's verdict ("Semantic convergence ...
passed") is recorded separately from the file-level outcome.
"""

import re
import time

from common import TempRoot, emit, make_workspace, run, summarize_ms

N_AGENTS = 15
REPS = 3

BASE_GO = """package server

type Server struct {
\trunning bool
}

func NewServer() *Server {
\treturn &Server{}
}

// AGENTS_INSERT_HERE
"""


def make_branch(ws, i, scenario):
    run(["git", "checkout", "-qb", f"agent_{i}", "main"], ws, check=True)
    if scenario == "disjoint":
        (ws / f"agent_{i}_file.go").write_text(f"package server\n\nfunc Agent{i}() {{}}\n")
        run(["git", "add", "-A"], ws, check=True)
    elif scenario == "same_anchor":
        src = (ws / "server.go").read_text()
        src = src.replace("// AGENTS_INSERT_HERE",
                          f"func (s *Server) Method{i}() {{}}\n\n// AGENTS_INSERT_HERE")
        (ws / "server.go").write_text(src)
    elif scenario == "diff_functions":
        with open(ws / "server.go", "a") as f:
            f.write(f"\nfunc (s *Server) Agent{i}Method() {{ s.running = true }}\n")
    run(["git", "commit", "-qam", f"agent {i} {scenario}"], ws, check=True)
    run(["git", "checkout", "-q", "main"], ws, check=True)


def tree_conflicted(ws):
    code, out, _ = run(["git", "status", "--porcelain"], ws)
    unmerged = any(line[:2] in ("UU", "AA", "DD", "AU", "UA", "DU", "UD")
                   for line in out.splitlines())
    markers = False
    sg = ws / "server.go"
    if sg.exists() and "<<<<<<<" in sg.read_text():
        markers = True
    return unmerged or markers


def expected_symbol(i, scenario):
    """The definition branch `i` adds under `scenario`."""
    return {"disjoint": f"func Agent{i}()",
            "same_anchor": f"func (s *Server) Method{i}()",
            "diff_functions": f"func (s *Server) Agent{i}Method()"}[scenario]


def change_landed(ws, i, scenario):
    """Whether branch `i`'s own change is present in the merged tree."""
    path = ws / (f"agent_{i}_file.go" if scenario == "disjoint" else "server.go")
    try:
        return expected_symbol(i, scenario) in path.read_text()
    except OSError:
        return False


def head_of(ws):
    code, out, _ = run(["git", "rev-parse", "HEAD"], ws)
    return out.strip() if code == 0 else None


def symbol_inventory(ws):
    """Every `func` definition in the merged tree's Go files."""
    found = set()
    for path in sorted(ws.glob("*.go")):
        try:
            text = path.read_text()
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("func "):
                found.add(line.split("{")[0].strip())
    return found


def merge_all(ws, arm, scenario="diff_functions"):
    per_branch, latencies = [], []
    exit_code_lies = 0
    for i in range(1, N_AGENTS + 1):
        head_before = head_of(ws)
        t0 = time.monotonic()
        if arm == "git":
            code, out, _ = run(["git", "merge", "-q", "--no-edit", f"agent_{i}"], ws)
        else:
            code, out, _ = run(["nool", "merge", f"agent_{i}", "--compact"], ws)
        ms = (time.monotonic() - t0) * 1000.0
        conflicted = tree_conflicted(ws)
        head_after = head_of(ws)
        landed = change_landed(ws, i, scenario)
        head_advanced = head_after is not None and head_after != head_before
        success = code == 0 and not conflicted and landed and head_advanced
        # 6.13/6.14.0 print "Semantic convergence ... passed"; 6.14.1 reworded
        # to "Semantic convergence checked (...)". Match both.
        semantic_pass = bool(re.search(
            r"Semantic convergence .*passed|Semantic convergence checked",
            out)) if arm == "nool" else None
        reconciled = bool(re.search(r"\[MergeReconcile\] Unioned", out)) \
            if arm == "nool" else None
        if conflicted and code == 0:
            exit_code_lies += 1
        if conflicted:
            run(["git", "merge", "--abort"], ws)
            if tree_conflicted(ws):  # abort didn't clean up — hard reset to keep going
                run(["git", "checkout", "-f", "main"], ws)
        latencies.append(ms)
        per_branch.append({"branch": i, "clean": not conflicted,
                           "tree_clean": not conflicted, "landed": landed,
                           "head_advanced": head_advanced, "success": success,
                           "silent_noop": code == 0 and not conflicted and not landed,
                           "exit_code": code, "semantic_layer_pass": semantic_pass,
                           "merge_reconcile_union": reconciled})
    return per_branch, latencies, exit_code_lies


def run_cell(root, scenario, arm, rep):
    ws = make_workspace(root, f"{scenario}_{arm}_{rep}", nool=False)
    (ws / "server.go").write_text(BASE_GO)
    # A module root so `go vet` can judge the merged tree in both arms.
    (ws / "go.mod").write_text("module bench\n\ngo 1.21\n")
    run(["git", "add", "-A"], ws, check=True)
    run(["git", "commit", "-qm", "base"], ws, check=True)
    if arm == "nool":
        code, out, _ = run(["nool", "init"], ws)
        if code != 0:
            raise RuntimeError(out)
    for i in range(1, N_AGENTS + 1):
        make_branch(ws, i, scenario)
    per_branch, latencies, lies = merge_all(ws, arm, scenario)
    clean = sum(1 for b in per_branch if b["tree_clean"])
    successes = sum(1 for b in per_branch if b["success"])
    expected = {expected_symbol(i, scenario) for i in range(1, N_AGENTS + 1)}
    inventory = symbol_inventory(ws)
    vet_code, vet_out, _ = run(["go", "vet", "./..."], ws)
    cell = {
        "clean_merges": clean,
        "successful_merges": successes,
        "conflicts": N_AGENTS - clean,
        "silent_noops": sum(1 for b in per_branch if b["silent_noop"]),
        "refused": sum(1 for b in per_branch if b["exit_code"] != 0),
        "inventory_present": len(expected & inventory),
        "inventory_complete": expected <= inventory,
        "vet_exit": vet_code,
        "vet_tail": vet_out.strip().splitlines()[-2:],
        "merge_latency": summarize_ms(latencies),
        "exit0_despite_conflict": lies,
        "branches": per_branch,
    }
    if arm == "nool":
        sem = [b["semantic_layer_pass"] for b in per_branch]
        cell["semantic_layer_passes"] = sum(1 for s in sem if s)
        cell["semantic_pass_but_file_conflict"] = sum(
            1 for b in per_branch if b["semantic_layer_pass"] and not b["clean"])
        cell["merge_reconcile_unions"] = sum(
            1 for b in per_branch if b["merge_reconcile_union"])
    return cell


def main():
    cells = {}
    with TempRoot("b5") as root:
        for scenario in ("disjoint", "same_anchor", "diff_functions"):
            for arm in ("git", "nool"):
                reps = []
                for rep in range(REPS):
                    reps.append(run_cell(root, scenario, arm, rep))
                    print(f"[b5] {scenario}/{arm} rep {rep} done")
                cells[f"{scenario}_{arm}"] = reps
    emit("b5_swarm_merge", {
        "config": {"n_agents": N_AGENTS, "reps": REPS,
                   "success_criterion": "exit 0 AND tree clean AND HEAD advanced AND "
                                        "the branch's own change present in the merged tree; "
                                        "inventory and go vet recorded after the last merge"},
        "cells": cells,
    })


if __name__ == "__main__":
    main()
