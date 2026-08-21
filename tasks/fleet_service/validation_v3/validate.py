#!/usr/bin/env python3
"""Validate corpus v3: per-cluster workspaces + grand workspace.

Guarantee sought: every accept test passes when its ticket (and only the
relevant cluster) is correctly implemented, AND when all 60 are implemented
simultaneously. This is the check that would have caught both t2 artifacts.
"""
import os, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
ROOT = os.path.join(tempfile.gettempdir(), "fleetsvc_v3_ws")

CLUSTERS = {
    "billing": (refs.apply_billing, ["t2", "t9", "t10", "t11", "t21", "t22"]),
    "api":     (refs.apply_api,     ["t3", "t7", "t12", "t13", "t14", "t23", "t24", "t38", "t39", "t40"]),
    "store":   (refs.apply_store,   ["t4", "t15", "t16", "t17", "t25", "t26"]),
    "users":   (refs.apply_users,   ["t1", "t6", "t20", "t27", "t28", "t29", "t36", "t37"]),
    "orders":  (lambda ws: (refs.apply_orders(ws), refs.apply_users(ws)),
                            ["t5", "t18", "t30", "t31", "t32"]),
    "ids":     (refs.apply_ids,     ["t8", "t33", "t34", "t35"]),
    "fillers": (refs.apply_fillers, [f"t{i}" for i in range(41, 61)]),
}
ALL = [f"t{i}" for i in range(1, 61)]

def accept_src(tid):
    d = os.path.join(REPO, "tasks/fleet_service/accept", tid)
    assert os.path.isdir(d), f"missing accept test for {tid}"
    return d

def copy_tests(ws, tids):
    for tid in tids:
        dst = os.path.join(ws, "accept", tid)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(accept_src(tid), dst)

def go_test(ws, target):
    r = subprocess.run(["go", "test", target], cwd=ws, capture_output=True, text=True, timeout=300)
    return r.returncode == 0, (r.stdout + r.stderr)

def run_ws(name, apply_fn, tids, smoke):
    ws = refs.new_ws(ROOT, name)
    apply_fn(ws)
    copy_tests(ws, tids)
    failures = []
    for tid in tids:
        ok, out = go_test(ws, f"./accept/{tid}/")
        if not ok:
            failures.append((tid, out.strip().splitlines()[-12:]))
    if smoke:
        ok, out = go_test(ws, ".")
        if not ok:
            failures.append(("smoke", out.strip().splitlines()[-12:]))
    return failures

def main():
    os.makedirs(ROOT, exist_ok=True)
    total_fail = 0
    only = sys.argv[1:] or None
    for name, (fn, tids) in CLUSTERS.items():
        if only and name not in only and "grand" not in only:
            continue
        if only and name not in only:
            continue
        fails = run_ws(name, fn, tids, smoke=False)
        status = "OK" if not fails else f"FAIL {[f[0] for f in fails]}"
        print(f"[cluster {name}] {len(tids)} tests: {status}")
        for tid, tail in fails:
            print(f"  --- {tid} ---")
            for line in tail:
                print(f"  {line}")
        total_fail += len(fails)
    if not only or "grand" in (only or []):
        fails = run_ws("grand", refs.apply_all, ALL, smoke=True)
        status = "OK" if not fails else f"FAIL {[f[0] for f in fails]}"
        print(f"[grand] {len(ALL)} tests + smoke: {status}")
        for tid, tail in fails:
            print(f"  --- {tid} ---")
            for line in tail:
                print(f"  {line}")
        total_fail += len(fails)
    print(f"TOTAL FAILURES: {total_fail}")
    sys.exit(1 if total_fail else 0)

if __name__ == "__main__":
    main()
