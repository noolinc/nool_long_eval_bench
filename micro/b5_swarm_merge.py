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

Success detection is by working-tree state (conflict markers / unmerged
paths), never exit codes; pilot probing showed `nool merge` can exit 0 on a
conflicted merge, so exit-code reliability is itself recorded.
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


def merge_all(ws, arm):
    per_branch, latencies = [], []
    exit_code_lies = 0
    for i in range(1, N_AGENTS + 1):
        t0 = time.monotonic()
        if arm == "git":
            code, out, _ = run(["git", "merge", "-q", "--no-edit", f"agent_{i}"], ws)
        else:
            code, out, _ = run(["nool", "merge", f"agent_{i}", "--compact"], ws)
        ms = (time.monotonic() - t0) * 1000.0
        conflicted = tree_conflicted(ws)
        semantic_pass = bool(re.search(r"Semantic convergence .* passed", out)) \
            if arm == "nool" else None
        if conflicted and code == 0:
            exit_code_lies += 1
        if conflicted:
            run(["git", "merge", "--abort"], ws)
            if tree_conflicted(ws):  # abort didn't clean up — hard reset to keep going
                run(["git", "checkout", "-f", "main"], ws)
        latencies.append(ms)
        per_branch.append({"branch": i, "clean": not conflicted,
                           "exit_code": code, "semantic_layer_pass": semantic_pass})
    return per_branch, latencies, exit_code_lies


def run_cell(root, scenario, arm, rep):
    ws = make_workspace(root, f"{scenario}_{arm}_{rep}", nool=False)
    (ws / "server.go").write_text(BASE_GO)
    run(["git", "add", "-A"], ws, check=True)
    run(["git", "commit", "-qm", "base"], ws, check=True)
    if arm == "nool":
        code, out, _ = run(["nool", "init"], ws)
        if code != 0:
            raise RuntimeError(out)
    for i in range(1, N_AGENTS + 1):
        make_branch(ws, i, scenario)
    per_branch, latencies, lies = merge_all(ws, arm)
    clean = sum(1 for b in per_branch if b["clean"])
    cell = {
        "clean_merges": clean,
        "conflicts": N_AGENTS - clean,
        "merge_latency": summarize_ms(latencies),
        "exit0_despite_conflict": lies,
    }
    if arm == "nool":
        sem = [b["semantic_layer_pass"] for b in per_branch]
        cell["semantic_layer_passes"] = sum(1 for s in sem if s)
        cell["semantic_pass_but_file_conflict"] = sum(
            1 for b in per_branch if b["semantic_layer_pass"] and not b["clean"])
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
        "config": {"n_agents": N_AGENTS, "reps": REPS},
        "cells": cells,
    })


if __name__ == "__main__":
    main()
