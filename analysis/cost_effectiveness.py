#!/usr/bin/env python3
"""Cost-effectiveness layer over results/trackc/fleet_runs.jsonl.

Turns the fleet records into the economic comparison the suite's outcome
claim C5 actually needs but `cost_usd` alone cannot give: cost per ACCEPTED
ticket once the costs of what went wrong are priced in. Every record already
carries the ingredients -- LLM spend, unaccepted tickets, merge conflicts,
main-branch poisonings, wall time -- so this module adds no data, only a
parameterised model over data that exists.

Per run, for a parameter vector (C_rework, C_poison, C_hour, fee):

    total  = llm_usd + fee + failed * C_rework
           + poisonings * C_poison + wall_hours * C_hour
    per_accepted = total / accepted

    failed      = tickets - accepted           (rework the enterprise must do)
    poisonings  = broken_main_merges           (team-blocking main breakage)
    wall_hours  = wall_ms / 3.6e6              (fleet latency, priced per hour)
    fee         = per-run charge for the coordination layer (nool arms only)

The unknown that decides the question is C_rework: what one failed ticket
costs the organisation to redo. Rather than assume it, this module reports
the BREAK-EVEN value C* at which the nool arm's cost per accepted ticket
equals the git arm's, per matched cell, and a sweep of per-accepted cost at
several C_rework values so the reader can place their own number on the
curve. With per-run means A (everything except the rework term), F (failed)
and acc (accepted):

    C* = (A_git * acc_nool - A_nool * acc_git) / (F_nool * acc_git - F_git * acc_nool)

A non-positive denominator means the nool arm does not fail fewer tickets
per accepted ticket than the git arm, so no rework price makes it cheaper;
that is reported as such, never as a number.

Conflicts are reported alongside but NOT priced by default: an unaccepted
ticket already carries C_rework, and a conflict that was retried into
acceptance costs harness time that `wall_hours` already prices. Pricing
conflicts separately would double count. `--c-conflict` exists for readers
who disagree, and is 0 unless set.

This module emits numbers only. It draws no conclusion about whether nool
is worth buying -- that depends on C_rework, which is the reader's number.
"""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results" / "trackc"

# Arm pairs, git first. Order and membership follow protocols/fleet_v4.json:
# the primary comparisons, then the mechanism pairs, then the 8g planner
# pair (added 2026-09-06, spec 8g) and the raw policy pair.
DEFAULT_PAIRS = [
    ("git_competitive", "nool_gated"),
    ("git_competitive", "nool_try"),
    ("git_scheduled", "nool_gated"),
    ("git_planned", "nool_planned"),
    ("git_fleet", "nool_fleet"),
]


def load_runs(path):
    runs = []
    for line in path.read_text().splitlines():
        if line.strip():
            runs.append(json.loads(line))
    return runs


def cell_key(r):
    noise = r.get("footprint_noise") or {}
    return (r.get("model") or "?",
            r.get("corpus") or "v1",
            r.get("n_workers"),
            float(noise.get("drop") or 0.0),
            float(noise.get("add") or 0.0),
            r.get("ticket_tier") or "all")


def per_run(r):
    """Extract the priced ingredients from one record, deriving from the
    raw integration list where an older record lacks the evolution
    summary. Nothing is estimated: a field that cannot be derived is
    None and the run is excluded from any component that needs it."""
    acc_map = r.get("acceptance") or {}
    tickets = len(acc_map)
    accepted = sum(1 for v in acc_map.values() if v)
    ev = r.get("evolution") or {}
    integ = r.get("integration") or []
    if "conflicts" in ev:
        conflicts = ev["conflicts"]
    elif integ:
        conflicts = sum(1 for i in integ if not i.get("clean", True))
    else:
        conflicts = None
    if "broken_main_merges" in ev:
        poisonings = ev["broken_main_merges"]
    else:
        fh = r.get("final_health") or {}
        poisonings = 0 if (fh.get("build_ok") and fh.get("smoke_ok")) else 1
    return {
        "run_id": r.get("run_id"),
        "arm": r.get("arm"),
        "nool_version": r.get("nool_version"),
        "tickets": tickets,
        "accepted": accepted,
        "failed": tickets - accepted,
        "conflicts": conflicts,
        "poisonings": poisonings,
        "wall_hours": (r.get("wall_ms") or 0) / 3.6e6,
        "llm_usd": r.get("cost_usd") or 0.0,
    }


def arm_means(rows):
    """Mean of each ingredient over the reps of one arm in one cell."""
    keys = ("tickets", "accepted", "failed", "conflicts", "poisonings",
            "wall_hours", "llm_usd")
    out = {"reps": len(rows)}
    for k in keys:
        vals = [x[k] for x in rows if x[k] is not None]
        out[k] = statistics.fmean(vals) if vals else None
        out[k + "_sd"] = (statistics.stdev(vals) if len(vals) > 1 else 0.0) if vals else None
    out["accepted_list"] = [x["accepted"] for x in rows]
    return out


def fixed_part(m, c_poison, c_hour, c_conflict, fee):
    """Everything in the per-run total except the rework term."""
    a = m["llm_usd"] + fee + m["wall_hours"] * c_hour
    if m["poisonings"] is not None:
        a += m["poisonings"] * c_poison
    if m["conflicts"] is not None:
        a += m["conflicts"] * c_conflict
    return a


def per_accepted(m, c_rework, c_poison, c_hour, c_conflict, fee):
    if not m["accepted"]:
        return None
    return (fixed_part(m, c_poison, c_hour, c_conflict, fee)
            + m["failed"] * c_rework) / m["accepted"]


def break_even(mg, mn, c_poison, c_hour, c_conflict, fee_nool):
    """C_rework at which nool's per-accepted cost equals git's. Returns
    (value, status): status is 'crossover' when a positive C* exists,
    'nool_never_cheaper' when nool fails no fewer per accepted ticket,
    'nool_always_cheaper' when nool is cheaper at C_rework = 0 and the
    gap only widens."""
    if not mg["accepted"] or not mn["accepted"]:
        return None, "undefined"
    a_g = fixed_part(mg, c_poison, c_hour, c_conflict, 0.0)
    a_n = fixed_part(mn, c_poison, c_hour, c_conflict, fee_nool)
    denom = mn["failed"] * mg["accepted"] - mg["failed"] * mn["accepted"]
    numer = a_g * mn["accepted"] - a_n * mg["accepted"]
    if denom >= 0:
        # nool does not fail fewer per accepted; cheaper only if already
        # cheaper at C=0 with a non-widening gap.
        at_zero_n = a_n / mn["accepted"]
        at_zero_g = a_g / mg["accepted"]
        if denom == 0 and at_zero_n <= at_zero_g:
            return 0.0, "nool_always_cheaper"
        return None, "nool_never_cheaper"
    c_star = numer / denom
    if c_star <= 0:
        return 0.0, "nool_always_cheaper"
    return c_star, "crossover"


def fmt(x, nd=2):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs", default=str(RESULTS / "fleet_runs.jsonl"))
    ap.add_argument("--c-poison", type=float, default=0.0,
                    help="USD per main-branch poisoning event (default 0)")
    ap.add_argument("--c-hour", type=float, default=0.0,
                    help="USD per hour of fleet wall time (default 0)")
    ap.add_argument("--c-conflict", type=float, default=0.0,
                    help="USD per merge conflict, additive (default 0; see doc)")
    ap.add_argument("--fee", type=float, default=0.0,
                    help="USD per run charged to nool arms (default 0)")
    ap.add_argument("--sweep", default="0,25,50,100,250,500,1000,2500",
                    help="comma-separated C_rework values for the per-accepted sweep")
    ap.add_argument("--pairs", default=None,
                    help="git:nool[,git:nool...] to override the default arm pairs")
    ap.add_argument("--model", default=None, help="restrict to one model id")
    ap.add_argument("--min-reps", type=int, default=1,
                    help="skip cells where either arm has fewer reps")
    ap.add_argument("--json", default=None, help="write full results here")
    args = ap.parse_args()

    sweep = [float(x) for x in args.sweep.split(",") if x.strip()]
    pairs = DEFAULT_PAIRS
    if args.pairs:
        pairs = [tuple(p.split(":")) for p in args.pairs.split(",")]

    runs = load_runs(Path(args.runs))
    cells = defaultdict(lambda: defaultdict(list))
    for r in runs:
        if not r.get("acceptance"):
            continue
        if args.model and r.get("model") != args.model:
            continue
        cells[cell_key(r)][r.get("arm")].append(per_run(r))

    print("cost-effectiveness over", len(runs), "fleet records")
    print(f"parameters: C_poison={args.c_poison} C_hour={args.c_hour} "
          f"C_conflict={args.c_conflict} fee_nool={args.fee}")
    print("per-accepted = (llm + fee + failed*C_rework + poisonings*C_poison"
          " + wall_h*C_hour + conflicts*C_conflict) / accepted")
    print("C* = C_rework at which the two arms' per-accepted costs are equal")
    print()

    results = []
    for git_arm, nool_arm in pairs:
        header_done = False
        for key in sorted(cells, key=lambda k: (k[0], k[1], k[2] or 0, k[3], k[4], k[5])):
            arms = cells[key]
            if git_arm not in arms or nool_arm not in arms:
                continue
            mg, mn = arm_means(arms[git_arm]), arm_means(arms[nool_arm])
            if mg["reps"] < args.min_reps or mn["reps"] < args.min_reps:
                continue
            if not header_done:
                print(f"=== {git_arm}  vs  {nool_arm} ===")
                print(f"{'model':<18}{'corpus':<6}{'N':>4}{'noise':>10}  "
                      f"{'reps g/n':>9}  {'acc g/n':>13}  {'fail g/n':>11}  "
                      f"{'confl g/n':>11}  {'poison g/n':>11}  {'llm$/acc g/n':>15}  "
                      f"{'wall_h g/n':>13}  {'C* (USD/failed ticket)':>24}")
                header_done = True
            c_star, status = break_even(mg, mn, args.c_poison, args.c_hour,
                                        args.c_conflict, args.fee)
            model, corpus, n, drop, add, tier = key
            noise = f"d{drop:g}/a{add:g}"
            llm_g = mg["llm_usd"] / mg["accepted"] if mg["accepted"] else None
            llm_n = mn["llm_usd"] / mn["accepted"] if mn["accepted"] else None
            cstar_txt = (f"{c_star:,.0f}" if status == "crossover"
                         else status.replace("_", " "))
            print(f"{model[:17]:<18}{corpus:<6}{n:>4}{noise:>10}  "
                  f"{mg['reps']:>4}/{mn['reps']:<4}  "
                  f"{fmt(mg['accepted'],1):>6}/{fmt(mn['accepted'],1):<6}  "
                  f"{fmt(mg['failed'],1):>5}/{fmt(mn['failed'],1):<5}  "
                  f"{fmt(mg['conflicts'],1):>5}/{fmt(mn['conflicts'],1):<5}  "
                  f"{fmt(mg['poisonings'],2):>5}/{fmt(mn['poisonings'],2):<5}  "
                  f"{fmt(llm_g,3):>7}/{fmt(llm_n,3):<7}  "
                  f"{fmt(mg['wall_hours'],3):>6}/{fmt(mn['wall_hours'],3):<6}  "
                  f"{cstar_txt:>24}")
            sweep_rows = []
            for c in sweep:
                sweep_rows.append({
                    "c_rework": c,
                    "per_accepted_git": per_accepted(mg, c, args.c_poison, args.c_hour, args.c_conflict, 0.0),
                    "per_accepted_nool": per_accepted(mn, c, args.c_poison, args.c_hour, args.c_conflict, args.fee),
                })
            results.append({
                "pair": [git_arm, nool_arm],
                "cell": {"model": model, "corpus": corpus, "n_workers": n,
                         "noise_drop": drop, "noise_add": add, "tier": tier},
                "git": mg, "nool": mn,
                "break_even_c_rework": c_star, "break_even_status": status,
                "sweep": sweep_rows,
            })
        if header_done:
            print()

    # Sweep table for every cell: per-accepted cost at each C_rework.
    print("=== per-accepted cost sweep (USD per accepted ticket; git | nool) ===")
    print(f"{'pair @ cell':<58}" + "".join(f"{'C='+str(int(c)):>17}" for c in sweep))
    for res in results:
        c = res["cell"]
        label = (f"{res['pair'][0]}/{res['pair'][1]} "
                 f"{c['corpus']} N{c['n_workers']} d{c['noise_drop']:g}/a{c['noise_add']:g}")
        cols = []
        for s in res["sweep"]:
            g, n = s["per_accepted_git"], s["per_accepted_nool"]
            cols.append(f"{fmt(g,2):>7}|{fmt(n,2):<8}")
        print(f"{label[:57]:<58}" + "".join(f"{x:>17}" for x in cols))

    if args.json:
        Path(args.json).write_text(json.dumps({
            "parameters": {"c_poison": args.c_poison, "c_hour": args.c_hour,
                           "c_conflict": args.c_conflict, "fee_nool": args.fee,
                           "sweep": sweep},
            "cells": results}, indent=1, default=float))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
