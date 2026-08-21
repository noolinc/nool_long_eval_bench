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


def b6():
    d = load("b6_context_retrieval")
    if not d:
        return
    print("== B6 context retrieval (bytes an agent must ingest) ==")
    rows = []
    for k, v in d["queries"].items():
        if isinstance(v, dict):
            rows.append([k, v.get("bytes"), v.get("wall_ms"), v.get("hit")])
        else:
            rows.append([k, v, "-", "-"])
    table(rows, ["query", "bytes", "wall_ms", "hit"])


def b7():
    d = load("b7_regression_localization")
    if not d:
        return
    print("== B7 regression localization ==")
    rows = []
    for arm, v in d["arms"].items():
        rows.append([arm, v.get("culprit_found"),
                     v.get("knot_named_intent", "-"), v.get("wall_ms"),
                     v.get("bisect_steps", v.get("bisect_steps_reported"))])
    table(rows, ["arm", "correct", "named", "wall_ms", "steps"])


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


# Corpus v2 contention clusters (design spec §8a, scale-up 1): A = same
# function body (service/billing.go Invoice), B = same handler file,
# C = same store file. v1 runs have none of these tickets.
CLUSTERS = {"A": ["t9", "t10", "t11"], "B": ["t12", "t13", "t14"],
            "C": ["t15", "t16", "t17"]}


def trackd():
    p = RESULTS / "trackc" / "fleet_runs.jsonl"
    if not p.exists():
        return
    runs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    print("== Track D fleet runs ==")
    rows = []
    for r in runs:
        acc = r.get("acceptance", {})
        integ = r.get("integration", [])
        by_ticket = {i["ticket"]: i for i in integ}
        wasted = round(sum((r["agents"].get(t, {}).get("cost_usd") or 0)
                           for t, i in by_ticket.items() if not i["clean"]), 4)
        rows.append([r["run_id"][:32], r.get("nool_version", "?").replace("nool ", ""),
                     r.get("corpus", "v1"), r["n_workers"],
                     f"{sum(acc.values())}/{len(acc)}" if acc else "-",
                     f"{sum(1 for i in integ if i['clean'])}/{len(integ)}" if integ else "-",
                     round(r.get("wall_ms", 0) / 1000), r.get("cost_usd", "-"),
                     wasted])
    table(rows, ["run", "nool", "corpus", "wrk", "accepted", "clean_merges",
                 "wall_s", "usd", "wasted_usd"])

    v2 = [r for r in runs if r.get("corpus") == "v2"]
    if not v2:
        return
    print("== Track D per-cluster outcomes (corpus v2) ==")
    rows = []
    for r in v2:
        acc = r.get("acceptance", {})
        by_ticket = {i["ticket"]: i for i in r.get("integration", [])}
        for cname, tids in CLUSTERS.items():
            merged = sum(1 for t in tids if by_ticket.get(t, {}).get("clean"))
            passed = sum(1 for t in tids if acc.get(t))
            wasted = round(sum((r["agents"].get(t, {}).get("cost_usd") or 0)
                               for t in tids
                               if not by_ticket.get(t, {}).get("clean")), 4)
            rows.append([r["run_id"][:32], cname, f"{merged}/{len(tids)}",
                         f"{passed}/{len(tids)}", wasted])
    table(rows, ["run", "cluster", "clean_merges", "accepted", "wasted_usd"])


def main():
    for f in (b1, b2, b3, b4, b5, b6, b7, trackc, trackd):
        f()


if __name__ == "__main__":
    main()
