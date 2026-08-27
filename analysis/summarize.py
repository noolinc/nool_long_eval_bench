#!/usr/bin/env python3
"""Summarize all benchmark results under results/ as tables.

Reports numbers only. Interpretation belongs to the humans reading them.
Every figure printed here is regenerable from the committed raw JSON.
"""

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
REPO = Path(__file__).resolve().parent.parent


def _run_dimensions(r):
    """Protocol-v4 strata; defaults preserve readability of legacy runs."""
    noise = r.get("footprint_noise") or {}
    return {
        "repository": r.get("repository", "synthetic/fleet_service"),
        "language": r.get("language", "go"),
        "corpus": r.get("corpus", "v1"),
        "workers": r.get("n_workers"),
        "model": r.get("model", "?"),
        "harness": r.get("harness") or "claude",
        "tier": r.get("ticket_tier", "all"),
        "footprint_source": r.get("footprint_source", "author-oracle"),
        "noise": (noise.get("drop", 0.0), noise.get("add", 0.0)),
    }


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
    # Schema moved from one nool arm to nool_governed/nool_fast when both
    # governance paths were measured; render whichever keys are present.
    nool_arms = sorted(k for k in next(iter(d["cases"].values())) if k != "git")
    rows = []
    for case, arms in d["cases"].items():
        rows.append([case, "accepted" if arms["git"]["accepted"] else "rejected",
                     *(arms[k]["stage"] for k in nool_arms)])
    table(rows, ["case", "git", *nool_arms])


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
        named = v.get("knot_named_intent") or v.get("resolved_intent") or "-"
        rows.append([arm, v.get("culprit_found"), named, v.get("wall_ms"),
                     v.get("bisect_steps", v.get("bisect_steps_reported")),
                     v.get("attested_for", "-")])
    table(rows, ["arm", "correct", "named", "wall_ms", "steps", "via_attestation"])


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
        # Conditional acceptance (§8d): pass-rate among tickets that landed
        # — separates each ticket's own quality from later main damage.
        # Records predating the metric show "-".
        cond = r.get("acceptance_conditional")
        if cond:
            c_pass = sum(1 for v in cond.values() if v is True)
            c_landed = sum(1 for v in cond.values() if v is not None)
            cond_s = f"{c_pass}/{c_landed}"
        else:
            cond_s = "-"
        # Throughput (§8d): accepted tickets per wall-clock minute, so the
        # coordinated arms' serialization cost sits beside acceptance
        # rather than in a footnote. Derived for old records.
        tput = r.get("throughput_accepted_per_min")
        if tput is None and acc and r.get("wall_ms"):
            tput = round(sum(acc.values()) / (r["wall_ms"] / 60000.0), 2)
        dims = _run_dimensions(r)
        rows.append([r["run_id"][:32], r.get("nool_version", "?").replace("nool ", ""),
                     dims["repository"], dims["language"], dims["corpus"],
                     r["n_workers"],
                     ("-" if not r.get("footprint_noise") else
                      f"d{r['footprint_noise']['drop']:g}/a{r['footprint_noise']['add']:g}"),
                     f"{sum(acc.values())}/{len(acc)}" if acc else "-",
                     cond_s,
                     f"{sum(1 for i in integ if i['clean'])}/{len(integ)}" if integ else "-",
                     round(r.get("wall_ms", 0) / 1000),
                     tput if tput is not None else "-",
                     r.get("cost_usd", "-"),
                     wasted])
    table(rows, ["run", "nool", "repository", "lang", "corpus", "wrk",
                 "fp_noise", "accepted", "cond_acc",
                 "clean_merges", "wall_s", "acc_per_min", "usd",
                 "wasted_usd"])

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


def _wilson(k, n, z=1.96):
    """95% Wilson score interval for a binomial proportion."""
    import math
    if not n:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def trackd_quality():
    """Attribution-relevant decomposition of fleet runs (audit 2026-08-22).

    landed        = merge clean AND not rejected by a CI-gated queue.
    acc|landed    = acceptance conditional on the ticket's work reaching main
                    (separates agent quality from integration policy).
    cascade       = landed but not accepted (build/test poisoning reached it).
    acc_no_land   = accepted despite NOT landing — a corpus artifact signal
                    (the t21 class: a neighbor's change satisfies the test).
    ser_premium   = run wall time / longest single agent (the serialization
                    cost of gated dispatch; ~1 means no serialization).
    Wilson CIs treat tickets as independent, which cascade failures violate;
    the run, not the ticket, is the unit of inference across reps.
    """
    p = RESULTS / "trackc" / "fleet_runs.jsonl"
    if not p.exists():
        return
    runs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    runs = [r for r in runs if r.get("acceptance") and r.get("integration")]
    print("== Track D fleet quality decomposition ==")
    rows = []
    for r in runs:
        acc = r["acceptance"]
        by_ticket = {i["ticket"]: i for i in r["integration"]}
        landed = {t for t, i in by_ticket.items()
                  if i["clean"] and not i.get("queue_rejected")}
        accepted = {t for t, v in acc.items() if v}
        conflicts = sum(1 for i in r["integration"] if not i["clean"])
        q_rej = sum(1 for i in r["integration"] if i.get("queue_rejected"))
        cascade = len(landed - accepted)
        acc_no_land = sorted(accepted - landed)
        # Use the landing-commit test result when present.  Intersecting the
        # final-state result with landed would re-introduce the cascade bias
        # this metric exists to remove; retain the legacy derivation only for
        # historical records that predate conditional scoring.
        conditional = r.get("acceptance_conditional")
        if conditional:
            c_landed = sum(v is not None for v in conditional.values())
            cond = (f"{sum(v is True for v in conditional.values())}/{c_landed}"
                    if c_landed else "-")
        else:
            cond = f"{len(accepted & landed)}/{len(landed)}" if landed else "-"
        walls = [a.get("wall_ms") or 0 for a in r["agents"].values()]
        prem = (round(r["wall_ms"] / max(walls), 2)
                if walls and max(walls) else "-")
        k, n = len(accepted), len(acc)
        lo, hi = _wilson(k, n)
        rows.append([r["run_id"][:28], r.get("corpus", "v1"), r["n_workers"],
                     f"{k}/{n}", f"[{lo},{hi}]", conflicts, q_rej, cascade,
                     cond, ",".join(acc_no_land) or "-", prem])
    table(rows, ["run", "corpus", "wrk", "accepted", "wilson95", "conflict",
                 "q_rej", "cascade", "acc|landed", "acc_no_land",
                 "ser_premium"])


def _fisher_exact(a, b, c, d):
    """Two-sided Fisher exact p-value for [[a,b],[c,d]]. Pure stdlib."""
    import math
    def lg(n):
        return math.lgamma(n + 1)
    r1, r2, c1, c2, n = a + b, c + d, a + c, b + d, a + b + c + d

    def prob(x):
        return math.exp(lg(r1) + lg(r2) + lg(c1) + lg(c2)
                        - lg(n) - lg(x) - lg(r1 - x) - lg(c1 - x) - lg(c2 - r1 + x))
    p_obs = prob(a)
    total = 0.0
    for x in range(max(0, c1 - r2), min(r1, c1) + 1):
        px = prob(x)
        if px <= p_obs * (1 + 1e-9):
            total += px
    return min(1.0, total)


def _mannwhitney(xs, ys):
    """Mann-Whitney U for xs vs ys. Exact permutation enumeration when the
    assignment space is small (as it always is at current rep counts),
    normal approximation otherwise. Returns (U, p_two_sided)."""
    import itertools
    import math
    xs, ys = sorted(xs), sorted(ys)
    n, m = len(xs), len(ys)
    if not n or not m:
        return None, None
    pooled = [(v, 0 if i < n else 1) for i, v in enumerate(xs + ys)]
    pooled_vals = sorted(range(len(pooled)), key=lambda i: pooled[i][0])
    rank = [0.0] * len(pooled)
    i = 0
    while i < len(pooled_vals):
        j = i
        while j < len(pooled_vals) and pooled[pooled_vals[j]][0] == pooled[pooled_vals[i]][0]:
            j += 1
        avg = (i + 1 + j) / 2
        for k in range(i, j):
            rank[pooled_vals[k]] = avg
        i = j
    u_obs = sum(rank[i] for i in range(n)) - n * (n + 1) / 2

    def u_of(assign):
        xr = sum(rank[i] for i in range(len(assign)) if assign[i])
        return xr - n * (n + 1) / 2

    if n + m <= 18:
        count = total_le = 0
        extreme = abs(u_obs - n * m / 2)
        for assign in itertools.combinations(range(n + m), n):
            mask = [False] * (n + m)
            for i in assign:
                mask[i] = True
            u = u_of(mask)
            count += 1
            if abs(u - n * m / 2) >= extreme - 1e-9:
                total_le += 1
        return u_obs, total_le / count
    mu = n * m / 2
    sd = math.sqrt(n * m * (n + m + 1) / 12)
    z = (u_obs - mu) / sd
    p = math.erfc(abs(z) / math.sqrt(2))
    return u_obs, p


MIN_REPS_FOR_INFERENCE = 5


def trackd_inference():
    """Cross-rep arm inference for Track D (spec §3.7 statistics).

    Unit of inference is the RUN (Wilson caveat above). For each corpus/N
    cell with data from both arms: Mann-Whitney U on per-run accepted counts,
    wall time, and cost per accepted ticket. Every cell with fewer than
    MIN_REPS_FOR_INFERENCE reps per arm is explicitly labeled UNDERPOWERED;
    p-values are still printed so effect direction and magnitude are readable,
    per the spec's 'no p-value theater' rule.
    """
    p = RESULTS / "trackc" / "fleet_runs.jsonl"
    if not p.exists():
        return
    runs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    runs = [r for r in runs if r.get("acceptance") and r.get("integration")]
    cells = {}
    for r in runs:
        key = (r.get("corpus", "v1"), r["n_workers"],
               r.get("model", "?"))
        cells.setdefault(key, {}).setdefault(r["arm"], []).append(r)

    print("== Track D cross-rep arm inference (unit = run) ==")
    print("p-values from exact permutation Mann-Whitney where computable;")
    print("cells below %d reps/arm are labeled UNDERPOWERED regardless of"
          % MIN_REPS_FOR_INFERENCE)
    print("any p-value. Pooled-ticket tests are deliberately omitted:")
    print("tickets within a run are not independent (cascade failures).")
    print("Cells never mix models; git_fleet vs nool_fleet only.\n")
    rows = []
    for (corpus, n_workers, model), arms in sorted(cells.items()):
        g = arms.get("git_fleet", [])
        nl = arms.get("nool_fleet", [])
        if not g or not nl:
            continue
        underpowered = (len(g) < MIN_REPS_FOR_INFERENCE
                        or len(nl) < MIN_REPS_FOR_INFERENCE)
        tag = "UNDERPOWERED" if underpowered else ""
        acc = {a: [sum(r["acceptance"].values()) for r in rs]
               for a, rs in (("git", g), ("nool", nl))}
        wall = {a: [r.get("wall_ms") for r in rs] for a, rs in
                (("git", g), ("nool", nl))}
        cost = {a: [] for a in acc}
        for lbl, rs in (("git", g), ("nool", nl)):
            for r in rs:
                k = sum(r["acceptance"].values())
                if k and r.get("cost_usd"):
                    cost[lbl].append(r["cost_usd"] / k)
        _, p_acc = _mannwhitney(acc["git"], acc["nool"])
        _, p_wall = _mannwhitney(wall["git"], wall["nool"])
        _, p_cost = (_mannwhitney(cost["git"], cost["nool"])
                     if all(cost.values()) else (None, None))

        def fmt(vs):
            vs = sorted(v for v in vs if v is not None)
            return ",".join(str(round(v, 2)) for v in vs) or "-"

        rows.append([f"{corpus}/N={n_workers}", model,
                     f"{len(g)}v{len(nl)}",
                     fmt(acc["git"]), fmt(acc["nool"]),
                     round(p_acc, 4) if p_acc is not None else "-",
                     round(p_wall, 4) if p_wall is not None else "-",
                     round(p_cost, 4) if p_cost is not None else "-",
                     tag])
    table(rows, ["corpus/N", "model", "reps(g|n)", "acc_git/reps",
                 "acc_nool/reps", "p_acc", "p_wall", "p_cost/usd_acc",
                 "power"])


def trackd_stratified_inference():
    """Stratified exact permutation test across all same-model cells.

    Workaround for the 2-reps-per-cell power ceiling: cells (corpus, N)
    differ, but under H0 arms are exchangeable WITHIN each cell. Permuting
    arm labels inside every stratum jointly and enumerating the full
    product space gives an exact stratified p-value for 'nool accepts more
    than git' that pools all cells without assuming homogeneity between
    them — the standard response to 'no single cell is powered'.

    Statistic: sum over cells of (mean_git - mean_nool) accepted counts;
    two-sided p = P(|stat| >= |observed|) over all within-cell relabelings.
    Still run-level; still labeled with its rep count.
    """
    import itertools
    import math
    import random
    p = RESULTS / "trackc" / "fleet_runs.jsonl"
    if not p.exists():
        return
    runs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    runs = [r for r in runs if r.get("acceptance") and r.get("integration")]
    models = sorted({r.get("model", "?") for r in runs})
    for model in models:
        cells = {}
        for r in runs:
            if r.get("model", "?") != model:
                continue
            g_or_n = {"git_fleet": "g", "nool_fleet": "n"}.get(r["arm"])
            if not g_or_n:
                continue
            cells.setdefault((r.get("corpus", "v1"), r["n_workers"]),
                             {"g": [], "n": []})[g_or_n].append(
                                 sum(r["acceptance"].values()))
        usable = {k: v for k, v in cells.items() if v["g"] and v["n"]}
        if len(usable) < 2:
            continue

        strata = []
        for key, v in sorted(usable.items()):
            pooled = v["g"] + v["n"]
            ng = len(v["g"])
            obs = sum(pooled[:ng]) / ng - sum(pooled[ng:]) / len(v["n"])
            strata.append((key, pooled, ng, obs))
        obs_total = sum(s[3] for s in strata)

        assignment_count = math.prod(
            math.comb(len(pooled), ng) for _, pooled, ng, _ in strata)

        def statistic(choice):
            stat = 0.0
            for (key, pooled, ng, obs), idxs in zip(strata, choice):
                idxs = set(idxs)
                gs = [v for i, v in enumerate(pooled) if i in idxs]
                ns = [v for i, v in enumerate(pooled) if i not in idxs]
                stat += sum(gs) / ng - sum(ns) / len(ns)
            return stat

        exact_limit = 250_000
        if assignment_count <= exact_limit:
            combos = [itertools.combinations(range(len(pooled)), ng)
                      for _, pooled, ng, _ in strata]
            # combinations iterators cannot be replayed inside a product;
            # materializing is safe under the explicit total-space bound.
            space = itertools.product(*(list(c) for c in combos))
            extreme = total = 0
            for choice in space:
                total += 1
                if abs(statistic(choice)) >= abs(obs_total) - 1e-9:
                    extreme += 1
            method = "exact"
        else:
            # Fixed seed makes regenerated tables stable. Add-one correction
            # avoids a zero p-value from a finite Monte Carlo sample.
            rng = random.Random(20260827)
            total = 100_000
            extreme = 1
            for _ in range(total):
                choice = [rng.sample(range(len(pooled)), ng)
                          for _, pooled, ng, _obs in strata]
                if abs(statistic(choice)) >= abs(obs_total) - 1e-9:
                    extreme += 1
            total += 1
            method = "monte-carlo"
        print(f"== Stratified permutation ({model}) ==")
        print("(observed sum < 0 means nool_fleet accepts more than "
              "git_fleet across cells)")
        print("cells:", ", ".join(
            f"{key[0]}/N={key[1]}({ng}v{len(pooled) - ng})"
            for (key, pooled, ng, obs) in strata))
        print(f"relabeling space: {assignment_count:,}; method: {method}; "
              f"evaluated: {total:,}; observed mean-difference sum: "
              f"{obs_total:+.1f}")
        print(f"two-sided stratified p = {extreme}/{total:,} = "
              f"{extreme / total:.5f}\n")


def trackd_protocol_inference():
    """Frozen-v4 comparisons, stratified without cross-language pooling.

    This is deliberately separate from the historical git_fleet/nool_fleet
    table above. New primary evidence compares a competitive conventional
    workflow with native nool arms and includes repository, language,
    harness, tier, and footprint noise in the cell identity.
    """
    protocol_path = REPO / "protocols" / "fleet_v4.json"
    runs_path = RESULTS / "trackc" / "fleet_runs.jsonl"
    if not protocol_path.exists() or not runs_path.exists():
        return
    protocol = json.loads(protocol_path.read_text())
    comparisons = protocol["primary_comparisons"] + protocol.get(
        "mechanism_comparisons", [])
    min_reps = protocol["minimum_repetitions_per_arm_cell"]
    runs = [json.loads(line) for line in runs_path.read_text().splitlines()
            if line.strip()]
    runs = [r for r in runs if r.get("acceptance") and
            r.get("integration") and r.get("harness") != "scripted"]

    print("== Track D frozen-v4 comparisons (unit = run) ==")
    rows = []
    for left, right in comparisons:
        cells = {}
        for r in runs:
            if r.get("arm") not in (left, right):
                continue
            d = _run_dimensions(r)
            key = (d["repository"], d["language"], d["corpus"],
                   d["workers"], d["model"], d["harness"], d["tier"],
                   d["footprint_source"], d["noise"])
            cells.setdefault(key, {}).setdefault(r["arm"], []).append(r)
        for key, arms in sorted(cells.items(), key=lambda item: str(item[0])):
            ls, rs = arms.get(left, []), arms.get(right, [])
            if not ls or not rs:
                continue
            l_acc = [sum(r["acceptance"].values()) for r in ls]
            r_acc = [sum(r["acceptance"].values()) for r in rs]
            l_tput = [r.get("throughput_accepted_per_min") for r in ls
                      if r.get("throughput_accepted_per_min") is not None]
            r_tput = [r.get("throughput_accepted_per_min") for r in rs
                      if r.get("throughput_accepted_per_min") is not None]
            _, p_acc = _mannwhitney(l_acc, r_acc)
            _, p_tput = (_mannwhitney(l_tput, r_tput)
                         if l_tput and r_tput else (None, None))
            repo, lang, corpus, workers, model, harness, tier, fp_source, noise = key
            power = ("READY" if len(ls) >= min_reps and len(rs) >= min_reps
                     else "UNDERPOWERED")
            rows.append([
                f"{left} v {right}", repo, lang, corpus, workers, harness,
                model, tier, fp_source, f"d{noise[0]:g}/a{noise[1]:g}",
                f"{len(ls)}v{len(rs)}", str(l_acc), str(r_acc),
                round(p_acc, 4) if p_acc is not None else "-",
                round(p_tput, 4) if p_tput is not None else "-", power,
            ])
    if rows:
        table(rows, ["comparison", "repository", "lang", "corpus", "N",
                     "harness", "model", "tier", "fp_source", "noise", "reps",
                     "accepted_left", "accepted_right", "p_acc",
                     "p_throughput", "power"])
    else:
        print("No complete frozen-v4 comparison cells yet.\n")


def main():
    for f in (b1, b2, b3, b4, b5, b6, b7, trackc, trackd, trackd_quality,
              trackd_inference, trackd_stratified_inference,
              trackd_protocol_inference):
        f()


if __name__ == "__main__":
    main()
