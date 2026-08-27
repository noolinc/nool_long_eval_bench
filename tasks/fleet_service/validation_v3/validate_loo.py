#!/usr/bin/env python3
"""Corpus v3.1 within-cluster leave-one-out validation (spec §8d).

Closes the documented v3 gap (validate_negative.py header): a ticket whose
hidden acceptance test is satisfied by its own cluster-mates' changes — the
t21 accepted-without-landing class — could not be detected with monolithic
per-cluster references. With refs_v31's subset-parametrized generators the
full matrix is checkable:

  Check 1 (fidelity oracle): refs_v31.apply_enabled(ws, ALL) must produce a
  byte-identical tree to refs.apply_all(ws). Guarantees the decomposition
  didn't drift from the validated v3 references.

  Check 2 (LOO, per ticket t): on apply_enabled(ws, ALL - {t}):
    - `go build ./...` and `go test ./...` stay green (the variant is a
      coherent codebase, so a failing accept test below means the TEST
      discriminates, not that the tree is broken);
    - t's accept test FAILS (its own work is genuinely required);
    - every same-cluster sibling's accept test PASSES (removing t does not
      collaterally break its neighbors' acceptance).

Writes results/micro/corpus_v31_loo_validation.json; exits nonzero on any
violation. Runtime is dominated by ~60 go build/test cycles (~5-10 min).
"""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402
import refs_v31  # noqa: E402

REPO = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
STARTER = os.path.join(REPO, "tasks", "fleet_service", "starter")
ACCEPT = os.path.join(REPO, "tasks", "fleet_service", "accept")
ROOT = os.path.join(tempfile.gettempdir(), "fleetsvc_v31_loo")
OUT = os.path.join(REPO, "results", "micro", "corpus_v31_loo_validation.json")


def run(cmd, cwd, timeout=180):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)[-2000:]


def new_ws(name):
    ws = os.path.join(ROOT, name)
    if os.path.exists(ws):
        shutil.rmtree(ws)
    shutil.copytree(STARTER, ws)
    return ws


def accept_test(ws, tid):
    dst = os.path.join(ws, "accept", tid)
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(os.path.join(ACCEPT, tid), dst)
    code, out = run(["go", "test", f"./accept/{tid}/"], ws)
    shutil.rmtree(os.path.join(ws, "accept"))
    return code == 0, out


def tree_diff(a, b):
    diffs = []
    for root, _dirs, files in os.walk(a):
        for f in files:
            pa = os.path.join(root, f)
            rel = os.path.relpath(pa, a)
            pb = os.path.join(b, rel)
            if not os.path.exists(pb):
                diffs.append(f"only in A: {rel}")
            elif not filecmp.cmp(pa, pb, shallow=False):
                diffs.append(f"differs: {rel}")
    for root, _dirs, files in os.walk(b):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), b)
            if not os.path.exists(os.path.join(a, rel)):
                diffs.append(f"only in B: {rel}")
    return diffs


def main():
    os.makedirs(ROOT, exist_ok=True)
    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "fidelity": None, "loo": {}, "violations": []}

    # Check 1: fidelity oracle
    a = new_ws("grand_v3")
    refs.apply_all(a)
    b = new_ws("grand_v31")
    refs_v31.apply_enabled(b, refs_v31.ALL)
    diffs = tree_diff(a, b)
    report["fidelity"] = {"identical": not diffs, "diffs": diffs}
    if diffs:
        report["violations"].append(f"fidelity: {len(diffs)} file diffs")
        print("FIDELITY FAIL:", *diffs[:10], sep="\n  ")

    # Check 2: LOO matrix
    for tid in refs_v31.ALL:
        cname, siblings = refs_v31.cluster_of(tid)
        ws = new_ws(f"loo_{tid}")
        refs_v31.apply_enabled(ws, set(refs_v31.ALL) - {tid})
        entry = {"cluster": cname}
        bcode, bout = run(["go", "build", "./..."], ws)
        tcode, _ = run(["go", "test", "./..."], ws)
        entry["build_ok"] = bcode == 0
        entry["suite_ok"] = tcode == 0
        if bcode != 0:
            entry["build_tail"] = bout[-400:]
            report["violations"].append(f"{tid}: LOO variant does not build")
        else:
            own_pass, _ = accept_test(ws, tid)
            entry["own_test_fails"] = not own_pass
            if own_pass:
                report["violations"].append(
                    f"{tid}: accept test PASSES without its ticket "
                    f"(accepted-without-landing class, cluster {cname})")
            sib_fail = []
            for s in siblings:
                if s == tid:
                    continue
                ok, _ = accept_test(ws, s)
                if not ok:
                    sib_fail.append(s)
            entry["sibling_failures"] = sib_fail
            if sib_fail:
                report["violations"].append(
                    f"{tid}: removing it breaks siblings {sib_fail}")
            if tcode != 0:
                report["violations"].append(
                    f"{tid}: LOO variant suite red (smoke/unit)")
        report["loo"][tid] = entry
        flag = ("ok" if entry.get("own_test_fails") and not
                entry.get("sibling_failures") and entry["build_ok"]
                and entry["suite_ok"] else "VIOLATION")
        print(f"{tid:5s} [{cname:8s}] {flag}", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(report, f, indent=1, sort_keys=True)
    print(f"\n{len(report['violations'])} violation(s); report -> {OUT}")
    shutil.rmtree(ROOT, ignore_errors=True)
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
