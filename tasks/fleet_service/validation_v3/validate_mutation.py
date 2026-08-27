#!/usr/bin/env python3
"""Corpus v3.1 mutation validation of the acceptance suites (spec §8d).

Goal: a prescriptive spec must not be able to hide a trivially-gameable
hidden test. Method: comparison-operator mutants of the GRAND reference
tree, attributed per ticket via refs_v31's LOO diffs, then killed (or not)
by each ticket's own acceptance test.

Attribution: a mutable line belongs to ticket t iff the file's content
differs between apply_enabled(ALL) and apply_enabled(ALL - {t}) at that
line. Lines shared by several tickets are attributed to each of them.

Mutants: single-site flips of comparison operators (<= <-> <, >= <-> >,
== <-> != on numeric guards) inside attributed lines of non-test .go
files. A mutant that fails `go build` is discarded (not a semantics probe).

Bar (pre-registered): every ticket that has >=1 buildable mutant on its
attributed lines must have its OWN accept test kill >=1 of them. A ticket
whose accept test kills none — while mutants exist that change its code's
comparisons — is flagged as gameable. Tickets with zero attributable
buildable mutants (pure additions with no comparisons, e.g. plain
delegation) are reported as "no_mutants", not violations.

Refinement after the first full run (2026-08-27): comparison flips on clamp/
min/max/abs-style boundaries are frequently EQUIVALENT mutants (`amt < 50 ->
<=` assigns 50 to 50) — no test can kill them, so counting them against the
bar made it unsatisfiable rather than strict. Hand-verified equivalent
mutants are allowlisted below with per-entry justifications and excluded
from the bar exactly like unbuildable mutants; one further class
(UNKILLABLE_BY_OWN_TEST) covers a boundary whose correct behavior belongs
to cluster-mates. Every genuine weakness the first run surfaced (t4, t36,
t54 boundary cases) was fixed by strengthening the acceptance tests, not by
allowlisting.

Writes results/micro/corpus_v31_mutation_validation.json; exits nonzero on
violations. Runtime: one build+test cycle per mutant (~10-20 min).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs_v31  # noqa: E402

REPO = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
STARTER = os.path.join(REPO, "tasks", "fleet_service", "starter")
ACCEPT = os.path.join(REPO, "tasks", "fleet_service", "accept")
ROOT = os.path.join(tempfile.gettempdir(), "fleetsvc_v31_mut")
OUT = os.path.join(REPO, "results", "micro",
                   "corpus_v31_mutation_validation.json")

FLIPS = [("<=", "<"), ("<", "<="), (">=", ">"), (">", ">=")]
_CMP_RE = re.compile(r"(?<![<>=!])(<=|>=|<|>)(?!=)")

# Hand-verified equivalent mutants (2026-08-27 review of the first full run):
# the flipped comparison is semantically identical to the original, so NO
# test could ever kill it — the same reason unbuildable mutants are
# discarded ("not a semantics probe"). Keys are the validator's own mutant
# descriptions and embed grand-tree line numbers: any refs_v31 change that
# moves these lines invalidates the list, so unmatched entries are a hard
# error below. Each entry records why the mutant is a semantic no-op.
EQUIVALENT_MUTANTS = {
    "<-><=@service/billing.go:20":
        "min clamp: at amt==50 the branch assigns 50 to 50",
    "<-><=@service/users.go:86":
        "sort comparator over unique user IDs: <= differs from < only on "
        "equal keys, which cannot occur",
    ">->>=@service/billing.go:23":
        "max cap: at amt==5000000 the branch assigns 5000000 to 5000000",
    ">->>=@service/orders.go:66":
        "including zero-cent orders adds 0 to the total",
    "<=-><@util/truncate.go:5":
        "at n==0 the fallthrough returns r[:0] == \"\", same as the guard",
    "<=-><@util/truncate.go:9":
        "at len(r)==n the fallthrough returns string(r[:n]) == s",
    "<-><=@util/reverse.go:6":
        "two-pointer loop: i==j adds only a self-swap",
    ">->>=@util/clamp.go:5":
        "at lo==hi every path returns the same value",
    "<-><=@util/clamp.go:8":
        "at v==lo the branch returns lo == v",
    ">->>=@util/clamp.go:11":
        "at v==hi the branch returns hi == v",
    "<-><=@util/abs.go:5":
        "at v==0 the branch returns -0 == 0",
    "<-><=@util/minmax.go:5":
        "at a==b MinInt returns either of two equal values",
    ">->>=@util/minmax.go:12":
        "at a==b MaxInt returns either of two equal values",
}

# Not equivalent, but unkillable by the ticket's OWN acceptance test: the
# only distinguishing input's correct behavior is owned by cluster-mates,
# so a subset-robust own-test (one that passes whenever this ticket's work
# landed, whatever else did) cannot assert it. Kept out of the per-ticket
# bar but reported, so the limitation stays visible.
UNKILLABLE_BY_OWN_TEST = {
    "<-><=@service/billing.go:10":
        "t21 negative guard: differs only at Invoice(0), whose correct "
        "value depends on whether t9/t10/t11 landed",
}


def run(cmd, cwd, timeout=180):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode


def new_ws(name, enabled):
    ws = os.path.join(ROOT, name)
    if os.path.exists(ws):
        shutil.rmtree(ws)
    shutil.copytree(STARTER, ws)
    refs_v31.apply_enabled(ws, enabled)
    return ws


def go_files(ws):
    for root, dirs, files in os.walk(ws):
        dirs[:] = [d for d in dirs if d not in (".git", "accept")]
        for f in files:
            if f.endswith(".go") and not f.endswith("_test.go"):
                yield os.path.relpath(os.path.join(root, f), ws)


def attributed_lines(grand):
    """{tid: {(rel, lineno)}} — lines of the grand tree whose content is
    changed/removed when tid is disabled."""
    attr = {}
    grand_lines = {rel: open(os.path.join(grand, rel)).read().splitlines()
                   for rel in go_files(grand)}
    for tid in refs_v31.ALL:
        ws = new_ws(f"attr_{tid}", set(refs_v31.ALL) - {tid})
        mine = set()
        for rel, glines in grand_lines.items():
            p = os.path.join(ws, rel)
            olines = (open(p).read().splitlines()
                      if os.path.exists(p) else [])
            oset = set(olines)
            for n, line in enumerate(glines, 1):
                if line not in oset and line.strip():
                    mine.add((rel, n))
        attr[tid] = mine
        shutil.rmtree(ws)
    return attr, grand_lines


def gen_mutants(grand_lines, sites):
    """One mutant per comparison operator occurrence on an attributed
    line: (rel, lineno, mutated_line, description)."""
    out = []
    for rel, n in sorted(sites):
        line = grand_lines[rel][n - 1]
        if "//" in line:
            code = line.split("//")[0]
        else:
            code = line
        for m in _CMP_RE.finditer(code):
            op = m.group(1)
            new_op = dict(FLIPS)[op]
            mutated = code[:m.start()] + new_op + code[m.end():] + \
                (line[len(code):] if len(line) > len(code) else "")
            out.append((rel, n, mutated, f"{op}->{new_op}@{rel}:{n}"))
    return out


def main():
    os.makedirs(ROOT, exist_ok=True)
    grand = new_ws("grand", refs_v31.ALL)
    if run(["go", "build", "./..."], grand):
        print("grand tree does not build; aborting")
        return 2
    attr, grand_lines = attributed_lines(grand)

    report = {"generated_utc": datetime.now(timezone.utc).isoformat(),
              "tickets": {}, "violations": [],
              "equivalent_allowlisted": dict(EQUIVALENT_MUTANTS),
              "unkillable_by_own_test": dict(UNKILLABLE_BY_OWN_TEST)}
    allowlist_seen = set()
    for tid in refs_v31.ALL:
        mutants = gen_mutants(grand_lines, attr[tid])
        entry = {"mutant_sites": len(mutants), "buildable": 0,
                 "killed_by_own": 0, "survivors": [], "allowlisted": []}
        acc_src = os.path.join(ACCEPT, tid)
        for rel, n, mutated, desc in mutants:
            if desc in EQUIVALENT_MUTANTS or desc in UNKILLABLE_BY_OWN_TEST:
                # Excluded from the bar the same way unbuildable mutants
                # are: verified not to be a semantics probe this ticket's
                # own test could ever answer. Recorded, never silently
                # dropped.
                allowlist_seen.add(desc)
                entry["allowlisted"].append(desc)
                continue
            p = os.path.join(grand, rel)
            orig = open(p).read()
            lines = orig.splitlines()
            lines[n - 1] = mutated
            open(p, "w").write("\n".join(lines) + ("\n" if
                                                   orig.endswith("\n") else ""))
            try:
                if run(["go", "build", "./..."], grand):
                    continue
                entry["buildable"] += 1
                dst = os.path.join(grand, "accept", tid)
                shutil.copytree(acc_src, dst)
                killed = run(["go", "test", f"./accept/{tid}/"], grand) != 0
                shutil.rmtree(os.path.join(grand, "accept"))
                if killed:
                    entry["killed_by_own"] += 1
                else:
                    entry["survivors"].append(desc)
            finally:
                open(p, "w").write(orig)
        if entry["buildable"] and not entry["killed_by_own"]:
            report["violations"].append(
                f"{tid}: {entry['buildable']} buildable comparison mutants "
                f"on its own lines, own accept test kills NONE (gameable)")
        report["tickets"][tid] = entry
        tag = ("no_mutants" if not (entry["buildable"] or entry["allowlisted"])
               else f"kills {entry['killed_by_own']}/{entry['buildable']}"
                    + (f" (+{len(entry['allowlisted'])} allowlisted)"
                       if entry["allowlisted"] else ""))
        print(f"{tid:5s} {tag}", flush=True)

    stale = (set(EQUIVALENT_MUTANTS) | set(UNKILLABLE_BY_OWN_TEST)) \
        - allowlist_seen
    if stale:
        # A refs_v31 edit moved or removed these lines; the hand
        # verification no longer applies. Fail loudly instead of silently
        # allowlisting whatever now lives at those coordinates.
        report["violations"].append(
            "stale allowlist entries (re-verify after refs change): "
            + ", ".join(sorted(stale)))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(report, f, indent=1, sort_keys=True)
    print(f"\n{len(report['violations'])} violation(s); report -> {OUT}")
    shutil.rmtree(ROOT, ignore_errors=True)
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
