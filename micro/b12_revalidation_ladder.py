"""B12 — Revalidation and quarantine rates across an agent-count and overlap
ladder (Nool task f36857ee; architecture review 2026-10-20, experiment 5).

No LLM. Scripted writers land governed (`--full`) changes concurrently in ONE
shared nool workspace built from the fleet_service Go starter, so every seal
races other seals and the seal's region rule decides whether the candidate's
recorded Full verdict is still valid (`validation:region-fresh`) or must be
re-run (`validation:region-revalidated`).

Writers per cell (N writers in total):
  providers  min(3, N) writers, one per shared dependency file
             (store/memstore.go, util/ids.go, util/clock.go). Each loops
             "append one exported func to my file, land it" until every
             consumer is done, so dependency files keep changing while
             consumers seal.
  consumers  N - providers writers. Each creates one new package file
             ext/w<i>/w.go and lands it once. Overlap level sets how many
             consumers CALL a provider's file:
               low    0%   (stdlib only: no corpus edge at all)
               medium 50%
               high   100%

Designs (B12_DESIGN):
  modify (default) every consumer file is landed in the base first, so it is
         indexed with its imports; the consumer appends one func to it. This
         isolates the dependency walk.
  create every consumer lands a NEW file. A file with no indexed entity makes
         the region rule (spec 2026-11-11, condition 2) treat every
         concurrently touched path as stale, so this design measures that
         rule, not the dependency walk.
A writer retries exit 3 (contention, "safe to retry") up to three times, as
an agent would; `refused` counts the proposals still failing after that.

Treatment: NOOL_BENCH_REVERSE_ONLY=1 in the environment makes a
benchmark-only build of nool walk only the dependents of the declared paths
when computing the seal's stale region (the behaviour before task 90280876,
knot 45fbeb4e); unset, it also walks the forward dependency closure (after).
Both arms run the SAME binary, so the treatment is the only difference.
The production binary has no such switch: this probe needs the patched
build named in the result's provenance.

Per cell: seals per hour, region-fresh / region-revalidated / untagged
counts and revalidation share, quarantined candidates and quarantine share,
refused proposals, per-op latency, lock wait when the binary reports it,
and seconds per landed ticket (the no-LLM stand-in for cost per landed
ticket: scripted writers spend no tokens).

Run:  PATH=<patched nool dir>:$PATH python3 b12_revalidation_ladder.py
Env:  B12_N=10,25,50  B12_OVERLAP=low,medium,high  B12_ARMS=before,after
      B12_DESIGN=modify|create
"""

import concurrent.futures as cf
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

from common import ENV, REPO_ROOT, TempRoot, emit, run, summarize_ms

N_VALUES = [int(x) for x in os.environ.get("B12_N", "10,25,50").split(",")]
OVERLAPS = os.environ.get("B12_OVERLAP", "low,medium,high").split(",")
ARMS = os.environ.get("B12_ARMS", "before,after").split(",")
# create: each consumer lands a NEW file (no indexed entity yet, so the region rule's
#         new-file condition marks it stale on any concurrent landing).
# modify: each consumer's file is landed in the base (indexed, imports known) and the
#         consumer appends one func to it, isolating the dependency walk.
DESIGN = os.environ.get("B12_DESIGN", "modify")
MAX_CONTENTION_RETRIES = 3
CALL_SHARE = {"low": 0.0, "medium": 0.5, "high": 1.0}
STARTER = REPO_ROOT / "tasks" / "fleet_service" / "starter"
MODULE = "bench/fleetsvc"
# (file, import path, an expression that calls into that file)
PROVIDER_FILES = [
    ("store/memstore.go", "store", "store.NewMem()"),
    ("util/ids.go", "util", 'util.NewID("w")'),
    ("util/clock.go", "util", "util.Now()"),
]
PROPOSE_TIMEOUT_S = 1800
LOCK_WAIT_RE = re.compile(r"lock_wait_ms[=: ]+(\d+)")


def land(ws, path, intent, env, agent):
    """Land `path`; retry exit 3 (contention, "safe to retry") up to
    MAX_CONTENTION_RETRIES times as an agent would. Returns (rc, output, ms,
    lock waits, retries)."""
    t0 = time.monotonic()
    retries = 0
    while True:
        p = subprocess.run(
            ["nool", "propose", "--path", path, "--intent", intent,
             "--why", "b12 scripted writer", "--full", "--solidify",
             "--as-agent", agent],
            cwd=str(ws), env=env, text=True, timeout=PROPOSE_TIMEOUT_S,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if p.returncode != 3 or retries >= MAX_CONTENTION_RETRIES:
            break
        retries += 1
    ms = (time.monotonic() - t0) * 1000.0
    waits = [int(x) for x in LOCK_WAIT_RE.findall(p.stdout)]
    return p.returncode, p.stdout, ms, waits, retries


def consumer_source(i, calls):
    if calls is None:
        return (f"package w{i}\n\nimport \"strconv\"\n\n"
                f"// W{i} is a scripted consumer with no corpus edge.\n"
                f"func W{i}() string {{ return strconv.Itoa({i}) }}\n")
    _, pkg, expr = calls
    return (f"package w{i}\n\nimport \"{MODULE}/{pkg}\"\n\n"
            f"// W{i} is a scripted consumer of {pkg}.\n"
            f"func W{i}() any {{ return {expr} }}\n")


def setup(root, name):
    ws = Path(root) / name
    shutil.copytree(STARTER, ws)
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "bench@nool-benchmarks.local"],
                ["git", "config", "user.name", "Bench"],
                ["git", "add", "-A"], ["git", "commit", "-qm", "base service"]):
        run(cmd, ws, check=True)
    code, out, _ = run(["nool", "init"], ws, timeout=300)
    if code != 0:
        raise RuntimeError(f"nool init failed:\n{out}")
    return ws


def seed_consumers(ws, env, n_cons, consumer_calls):
    """modify design: land every consumer's file in one base knot so each is
    indexed with its imports before the race starts."""
    paths = []
    for i in range(n_cons):
        rel = f"ext/w{i}/w.go"
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(consumer_source(i, consumer_calls(i)))
        paths.append(rel)
    args = ["nool", "propose", "--intent", "b12 seed consumers", "--why", "b12 base",
            "--justification", "b12 seeds one new file per consumer in one base knot",
            "--full", "--solidify"]
    for rel in paths:
        args += ["--path", rel]
    p = subprocess.run(args, cwd=str(ws), env=env, text=True, timeout=PROPOSE_TIMEOUT_S,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        raise RuntimeError(f"seeding consumers failed:\n{p.stdout[-3000:]}")


def tags_by_intent(ws):
    db = sqlite3.connect(str(ws / ".nool" / "nool.db"))
    try:
        rows = db.execute(
            "select intent_string, metadata_tags from intent_records").fetchall()
    finally:
        db.close()
    out = {}
    for intent, tags in rows:
        try:
            out[intent] = json.loads(tags or "[]")
        except ValueError:
            out[intent] = []
    return out


def quarantined(ws, env):
    p = subprocess.run(["nool", "candidate", "list", "--quarantined", "--json"],
                       cwd=str(ws), env=env, text=True, timeout=120,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        data = json.loads(p.stdout)
    except ValueError:
        return None
    if isinstance(data, dict):
        data = data.get("candidates", data.get("quarantined", []))
    return len(data)


def run_cell(root, arm, n, overlap):
    ws = setup(root, f"{arm}_{overlap}_n{n}")
    env = dict(ENV)
    env.pop("NOOL_BENCH_REVERSE_ONLY", None)
    if arm == "before":
        env["NOOL_BENCH_REVERSE_ONLY"] = "1"
    providers = PROVIDER_FILES[:min(3, n)]
    n_cons = n - len(providers)
    n_calling = round(n_cons * CALL_SHARE[overlap])
    def consumer_calls(i):
        return providers[i % len(providers)] if i < n_calling else None

    if DESIGN == "modify":
        seed_consumers(ws, env, n_cons, consumer_calls)
    stop = threading.Event()
    ops = []  # (role, intent, rc, ms, retries)
    lock_waits = []
    mu = threading.Lock()

    def provider(k):
        path, _, _ = providers[k]
        op = 0
        while not stop.is_set():
            with open(ws / path, "a") as f:
                f.write(f"\n// P{k}Op{op} is appended by scripted provider {k}.\n"
                        f"func P{k}Op{op}() int {{ return {op} }}\n")
            intent = f"b12 provider {k} op {op}"
            rc, out, ms, waits, tries = land(ws, path, intent, env, f"prov{k}")
            with mu:
                ops.append(("provider", intent, rc, ms, tries))
                lock_waits.extend(waits)
            if rc != 0:
                # Keep the tree buildable for everyone else: drop the
                # refused append, then stop this provider.
                run(["git", "checkout", "--", path], ws)
                (ws / "b12_refusals.log").open("a").write(
                    f"--- {intent} rc={rc}\n{out[-3000:]}\n")
                return
            op += 1

    def consumer(i):
        rel = f"ext/w{i}/w.go"
        if DESIGN == "modify":
            with open(ws / rel, "a") as f:
                f.write(f"\n// W{i}b is appended by scripted consumer {i}.\n"
                        f"func W{i}b() int {{ return {i} }}\n")
        else:
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(consumer_source(i, consumer_calls(i)))
        intent = f"b12 consumer {i}"
        rc, out, ms, waits, tries = land(ws, rel, intent, env, f"cons{i}")
        with mu:
            ops.append(("consumer", intent, rc, ms, tries))
            lock_waits.extend(waits)
        if rc != 0:
            (ws / "b12_refusals.log").open("a").write(
                f"--- {intent} rc={rc}\n{out[-3000:]}\n")

    t0 = time.monotonic()
    with cf.ThreadPoolExecutor(max_workers=n) as ex:
        pfuts = [ex.submit(provider, k) for k in range(len(providers))]
        cfuts = [ex.submit(consumer, i) for i in range(n_cons)]
        for f in cfuts:
            f.result()
        stop.set()
        for f in pfuts:
            f.result()
    wall_s = time.monotonic() - t0

    tags = tags_by_intent(ws)
    counts = {"fresh": 0, "revalidated": 0, "untagged": 0}
    by_role = {r: {"fresh": 0, "revalidated": 0, "untagged": 0}
               for r in ("provider", "consumer")}
    landed = 0
    for role, intent, rc, _, _ in ops:
        if rc != 0:
            continue
        landed += 1
        t = tags.get(intent, [])
        key = ("revalidated" if "validation:region-revalidated" in t
               else "fresh" if "validation:region-fresh" in t else "untagged")
        counts[key] += 1
        by_role[role][key] += 1
    q = quarantined(ws, env)
    proposals = len(ops)
    refused = sum(1 for o in ops if o[2] != 0)
    build_ok = run(["go", "build", "./..."], ws)[0] == 0
    cell = {
        "arm": arm, "n": n, "overlap": overlap, "design": DESIGN,
        "contention_retries": sum(o[4] for o in ops),
        "providers": len(providers), "consumers": n_cons,
        "consumers_calling_a_provider": n_calling,
        "proposals": proposals, "landed": landed, "refused": refused,
        "wall_time_s": round(wall_s, 1),
        "seals_per_hour": round(landed / wall_s * 3600, 1) if wall_s else None,
        "seconds_per_landed_ticket": round(wall_s / landed, 2) if landed else None,
        "region": counts, "region_by_role": by_role,
        "revalidation_share": round(counts["revalidated"] / landed, 3) if landed else None,
        "consumer_revalidation_share": (
            round(by_role["consumer"]["revalidated"] / max(1, sum(by_role["consumer"].values())), 3)),
        "quarantined": q,
        "quarantine_share": round(q / proposals, 3) if (q is not None and proposals) else None,
        "lock_wait": summarize_ms(lock_waits) if lock_waits else "not reported by this binary",
        "op_latency": summarize_ms([o[3] for o in ops if o[2] == 0]),
        "final_tree_builds": build_ok,
    }
    if (ws / "b12_refusals.log").exists():
        cell["refusal_log_tail"] = (ws / "b12_refusals.log").read_text()[-4000:]
    return cell


def main():
    cells = {}
    with TempRoot("b12") as root:
        for n in N_VALUES:
            for overlap in OVERLAPS:
                for arm in ARMS:
                    key = f"{arm}_{overlap}_n{n}"
                    cells[key] = run_cell(root, arm, n, overlap)
                    c = cells[key]
                    print(f"[b12] {key}: landed {c['landed']}/{c['proposals']} "
                          f"reval {c['revalidation_share']} "
                          f"quar {c['quarantined']} {c['seals_per_hour']}/h",
                          flush=True)
    emit(f"b12_revalidation_ladder_{DESIGN}", {
        "config": {"design": DESIGN, "max_contention_retries": MAX_CONTENTION_RETRIES,
                   "n_values": N_VALUES, "overlaps": OVERLAPS, "arms": ARMS,
                   "call_share": CALL_SHARE,
                   "provider_files": [p[0] for p in PROVIDER_FILES],
                   "treatment": "NOOL_BENCH_REVERSE_ONLY=1 (before) vs unset (after)"},
        "cells": cells,
    })


if __name__ == "__main__":
    main()
