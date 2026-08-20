#!/usr/bin/env python3
"""Summarize all benchmark results under results/ as tables.

Reports numbers only. Interpretation belongs to the humans reading them.
Every figure printed here is regenerable from the committed raw JSON.
"""

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"


def load(name):
    p = RESULTS / "micro" / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def table(rows, headers):
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for r in rows:
        print(fmt.format(*[str(x) for x in r]))
    print()


def b1():
    d = load("b1_overhead")
    if not d:
        return
    print("== B1 overhead (medians, ms) ==")
    rows = [[h, v["median_ms"], v["p90_ms"]]
            for h, v in d["hook_latency_with_payload"].items()]
    table(rows, ["hook", "median_ms", "p90_ms"])
    rows = []
    for size, c in d["landing_a_change"].items():
        rows.append([size, c["git_add_commit"]["median_ms"],
                     c["nool_propose_fast_solidify"]["median_ms"],
                     c.get("nool_auto_justify_used", False), c["nool_nonzero_exits"]])
    table(rows, ["change", "git_ms", "nool_ms", "auto_justify", "nool_fails"])


def b2():
    d = load("b2_concurrency")
    if not d:
        return
    print("== B2 live concurrency (shared workspace) ==")
    rows = []
    for k, c in d["cells"].items():
        rows.append([k, c["wall_time_ms"], f"{c['ops_landed']}/{c['ops_expected']}",
                     c["ops_swept_into_other_commit"], c["total_retries"],
                     c["files_with_lost_updates"], c["history_entries_added"],
                     c["op_latency"]["median_ms"] if c["op_latency"] else "-"])
    table(rows, ["cell", "wall_ms", "landed", "swept", "retries", "lost",
                 "history+", "op_med_ms"])


def b3():
    d = load("b3_recovery")
    if not d:
        return
    print("== B3 recovery (remove bad landing, keep later unrelated work) ==")
    rows = []
    for variant, arms in d["variants"].items():
        for arm, reps in arms.items():
            if not reps:
                continue
            import statistics
            rows.append([variant, arm,
                         f"{sum(r['damage_removed'] for r in reps)}/{len(reps)}",
                         f"{sum(r['unrelated_work_survived'] for r in reps)}/{len(reps)}",
                         round(statistics.median(r["recovery_ms"] for r in reps), 1),
                         reps[0]["command_count"]])
    table(rows, ["variant", "arm", "damage_removed", "unrelated_survived",
                 "median_ms", "commands"])


def b4():
    d = load("b4_guardrails")
    if not d:
        return
    print("== B4 guardrails ==")
    rows = []
    for case, arms in d["cases"].items():
        rows.append([case, "accepted" if arms["git"]["accepted"] else "rejected",
                     arms["nool"]["stage"]])
    table(rows, ["case", "git", "nool"])


def b5():
    d = load("b5_swarm_merge")
    if not d:
        return
    n = d["config"]["n_agents"]
    print(f"== B5 swarm merge (N={n} branches, per-rep clean merges) ==")
    rows = []
    for cell, reps in d["cells"].items():
        clean = [r["clean_merges"] for r in reps]
        sem = [r.get("semantic_layer_passes", "-") for r in reps]
        semconf = [r.get("semantic_pass_but_file_conflict", "-") for r in reps]
        lies = [r["exit0_despite_conflict"] for r in reps]
        rows.append([cell, clean, sem, semconf, lies])
    table(rows, ["cell", "clean/rep", "semantic_pass", "sem_pass_but_conflict",
                 "exit0_on_conflict"])


def trackc():
    p = RESULTS / "trackc" / "runs.jsonl"
    if not p.exists():
        return
    runs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    print("== Track C runs ==")
    rows = []
    for r in runs:
        score = r.get("score", {})
        agents = r.get("agents") or ([r["agent"]] if "agent" in r else [])
        tok = sum((a.get("tokens_out") or 0) for a in agents) or "-"
        turns = sum((a.get("num_turns") or 0) for a in agents) or "-"
        cost = round(sum((a.get("cost_usd") or 0) for a in agents), 4) or "-"
        integ = r.get("integration")
        clean = f"{sum(1 for i in integ if i['clean'])}/{len(integ)}" if integ else "-"
        rows.append([r["run_id"][:40], r.get("model_requested", "?"),
                     score.get("build_ok"), score.get("tests_ok"), clean,
                     turns, tok, cost,
                     "FATAL" if "fatal_error" in r else ""])
    table(rows, ["run", "model", "build", "tests", "merges", "turns",
                 "tok_out", "usd", "err"])


def main():
    for f in (b1, b2, b3, b4, b5, trackc):
        f()


if __name__ == "__main__":
    main()
