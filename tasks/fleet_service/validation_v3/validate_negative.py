#!/usr/bin/env python3
"""Negative validation for corpus v3: acceptance tests must FAIL where their
ticket is not implemented.

validate.py proves the positive direction (every test passes when its ticket
is implemented, per-cluster and grand). This proves two negative directions:

  A) base:       every accept test fails on the plain starter tree;
  B) complement: every accept test fails when every OTHER cluster's reference
                 implementation is applied but its own cluster stays at
                 starter (catches cross-cluster satisfaction).

Not covered (documented limit, pre-registered as corpus v3.1 work): within-
cluster leave-one-out — a test satisfied by its own cluster-mates' changes
(the t21 class, observed empirically as accepted-without-landing in git_fleet
runs) requires per-ticket-decomposed references, which refs.py's monolithic
per-cluster files cannot express. The empirical detector for that class is
analysis/summarize.py's accepted-without-landing table.

Writes results/micro/corpus_v3_negative_validation.json; exits nonzero on any
violation (a test passing where it must fail) or non-evaluable complement.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
ROOT = os.path.join(tempfile.gettempdir(), "fleetsvc_v3_negative")
OUT = os.path.join(REPO, "results", "micro", "corpus_v3_negative_validation.json")

# Application order matches refs.apply_all.
PRIMS = ["billing", "users", "orders", "store", "api", "ids", "clock", "fillers"]
APPLY = {p: getattr(refs, f"apply_{p}") for p in PRIMS}
TICKETS = {
    "billing": ["t2", "t9", "t10", "t11", "t21", "t22"],
    "users":   ["t1", "t6", "t20", "t27", "t28", "t29", "t36", "t37"],
    "orders":  ["t5", "t18", "t30", "t31", "t32"],
    "store":   ["t4", "t15", "t16", "t17", "t25", "t26"],
    "api":     ["t3", "t7", "t12", "t13", "t14", "t23", "t24", "t38", "t39", "t40"],
    "ids":     ["t8", "t33", "t34", "t35"],
    "clock":   ["t19"],
    "fillers": [f"t{i}" for i in range(41, 61)],
}
ALL = [f"t{i}" for i in range(1, 61)]

# A primitive listed here cannot compile/behave without the ones it names
# (refs.apply_orders rewrites service/billing.go and pairs with users in
# validate.py). Excluding X also excludes, transitively, everything that
# requires X. Complement buildability is asserted below either way.
REQUIRES = {"orders": {"billing", "users"}}


def excluded_with(x):
    out = {x}
    changed = True
    while changed:
        changed = False
        for p, needs in REQUIRES.items():
            if p not in out and needs & out:
                out.add(p)
                changed = True
    return out


def go(ws, *args, timeout=300):
    r = subprocess.run(["go", *args], cwd=ws, capture_output=True, text=True,
                       timeout=timeout)
    return r.returncode == 0, (r.stdout + r.stderr)


def copy_test(ws, tid):
    src = os.path.join(REPO, "tasks/fleet_service/accept", tid)
    dst = os.path.join(ws, "accept", tid)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def must_fail(ws, tid):
    copy_test(ws, tid)
    ok, out = go(ws, "test", f"./accept/{tid}/")
    mode = "passed" if ok else (
        "build_error" if "build failed" in out or "undefined" in out
        or "cannot find" in out else "test_failure")
    return {"fails_as_required": not ok, "mode": mode}


def main():
    os.makedirs(ROOT, exist_ok=True)
    res = {
        "provenance": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "go_version": subprocess.run(["go", "version"], capture_output=True,
                                         text=True).stdout.strip(),
        },
        "base": {}, "complement": {}, "violations": [], "not_evaluable": [],
    }

    ws = refs.new_ws(ROOT, "base")
    for tid in ALL:
        r = must_fail(ws, tid)
        res["base"][tid] = r
        if not r["fails_as_required"]:
            res["violations"].append({"check": "base", "ticket": tid})
    n_bad = sum(1 for v in res["base"].values() if not v["fails_as_required"])
    print(f"[base] {len(ALL)} tests, {len(ALL)-n_bad} fail as required, "
          f"{n_bad} VIOLATIONS")

    for x in PRIMS:
        drop = excluded_with(x)
        ws = refs.new_ws(ROOT, f"complement_{x}")
        for p in PRIMS:
            if p not in drop:
                APPLY[p](ws)
        ok, out = go(ws, "build", "./...")
        entry = {"excluded": sorted(drop), "builds": ok, "tickets": {}}
        if not ok:
            entry["build_tail"] = out.strip().splitlines()[-6:]
            res["not_evaluable"].append(x)
            res["complement"][x] = entry
            print(f"[complement -{x}] NOT EVALUABLE (build broken)")
            continue
        bad = []
        for tid in TICKETS[x]:
            r = must_fail(ws, tid)
            entry["tickets"][tid] = r
            if not r["fails_as_required"]:
                bad.append(tid)
                res["violations"].append({"check": f"complement_{x}",
                                          "ticket": tid})
        res["complement"][x] = entry
        status = "OK" if not bad else f"VIOLATIONS {bad}"
        print(f"[complement -{x}] excluded={sorted(drop)} "
              f"{len(TICKETS[x])} tests: {status}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(res, f, indent=1)
    print(f"violations: {len(res['violations'])}  "
          f"not_evaluable: {res['not_evaluable']}  -> {OUT}")
    sys.exit(1 if res["violations"] or res["not_evaluable"] else 0)


if __name__ == "__main__":
    main()
