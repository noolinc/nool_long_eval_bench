"""B2 — Live concurrency (H3 mechanism): N writers land changes to disjoint
files in ONE shared workspace, concurrently.

git arm : each writer loops `git add <own file> && git commit` (index.lock is
          git's single-workspace coordination); lock failures retried.
nool arm: each writer loops `nool propose --path <own file> --fast --solidify`
          (ledger lock is nool's coordination); failures retried.

Metrics per (arm, N): wall time to all-done, per-op latency distribution,
retry counts, landed-op count vs expected, lost updates (file content check),
history integrity (commit/knot count).
"""

import concurrent.futures as cf
import json
import re
import subprocess
import time

from common import ENV, TempRoot, emit, make_workspace, run, summarize_ms

N_VALUES = [2, 5, 15]
OPS_PER_WRITER = 6
# Retry budget must exceed the full serialization window at the largest N
# (N*ops*op_cost), or the slower-locking arm reads as catastrophic failure
# when it is merely queueing. 200 * 50ms = 10s > 15*6*~100ms.
MAX_RETRIES = 200
RETRY_SLEEP_S = 0.05


def writer(ws, arm, wid):
    lat, retries = [], 0
    swept = 0
    path = f"writer_{wid}.txt"
    for op in range(OPS_PER_WRITER):
        with open(ws / path, "a") as f:
            f.write(f"writer {wid} op {op}\n")
        for attempt in range(MAX_RETRIES):
            t0 = time.monotonic()
            if arm == "git":
                p = subprocess.run(
                    ["bash", "-c", f"git add {path} && git commit -qm 'w{wid} op{op}'"],
                    cwd=str(ws), env=ENV, text=True, timeout=120,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            else:
                p = subprocess.run(
                    ["nool", "propose", "--path", path, "--intent", f"w{wid} op{op}",
                     "--fast", "--solidify", "--compact"],
                    cwd=str(ws), env=ENV, text=True, timeout=120,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            ms = (time.monotonic() - t0) * 1000.0
            if p.returncode == 0:
                lat.append(ms)
                break
            if arm == "git":
                # Shared-index sweep: another writer's commit may have carried
                # this writer's staged change. If this path is clean in the
                # tree, the change IS in history (under the other writer's
                # commit) — count it landed, attribution lost.
                q = subprocess.run(["git", "status", "--porcelain", "--", path],
                                   cwd=str(ws), env=ENV, text=True, timeout=60,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                if q.returncode == 0 and not q.stdout.strip():
                    lat.append(ms)
                    swept += 1
                    break
            retries += 1
            time.sleep(RETRY_SLEEP_S)
        else:
            return {"writer": wid, "latencies": lat, "retries": retries,
                    "swept_into_other_commit": swept, "gave_up_at": op}
    return {"writer": wid, "latencies": lat, "retries": retries,
            "swept_into_other_commit": swept, "gave_up_at": None}


def history_count(ws, arm):
    if arm == "git":
        code, out, _ = run(["git", "rev-list", "--count", "HEAD"], ws)
        return int(out.strip()) if code == 0 else -1
    code, out, _ = run(["nool", "log", "--json"], ws)
    try:
        return len(json.loads(out))
    except Exception:
        m = re.findall(r"Total Knots\s*:\s*(\d+)", out)
        return int(m[0]) if m else -1


def run_cell(root, arm, n):
    ws = make_workspace(root, f"{arm}_{n}", nool=(arm == "nool"))
    (ws / "README.txt").write_text("concurrency bench\n")
    if arm == "git":
        run(["bash", "-c", "git add -A && git commit -qm base"], ws, check=True)
    else:
        code, out, _ = run(["nool", "propose", "--all", "--intent", "base",
                            "--fast", "--solidify", "--compact"], ws)
        if code != 0:
            raise RuntimeError(out)
    base_history = history_count(ws, arm)

    t0 = time.monotonic()
    with cf.ThreadPoolExecutor(max_workers=n) as ex:
        results = list(ex.map(lambda w: writer(ws, arm, w), range(n)))
    wall_ms = (time.monotonic() - t0) * 1000.0

    all_lat = [ms for r in results for ms in r["latencies"]]
    landed = sum(len(r["latencies"]) for r in results)
    lost = 0
    for w in range(n):
        content = (ws / f"writer_{w}.txt").read_text()
        expected = "".join(f"writer {w} op {o}\n" for o in range(OPS_PER_WRITER))
        if content != expected:
            lost += 1
    return {
        "wall_time_ms": round(wall_ms, 1),
        "ops_expected": n * OPS_PER_WRITER,
        "ops_landed": landed,
        "writers_gave_up": sum(1 for r in results if r["gave_up_at"] is not None),
        "ops_swept_into_other_commit": sum(r["swept_into_other_commit"] for r in results),
        "total_retries": sum(r["retries"] for r in results),
        "op_latency": summarize_ms(all_lat),
        "files_with_lost_updates": lost,
        "history_entries_added": history_count(ws, arm) - base_history,
    }


def main():
    cells = {}
    with TempRoot("b2") as root:
        for arm in ("git", "nool"):
            for n in N_VALUES:
                cells[f"{arm}_n{n}"] = run_cell(root, arm, n)
                print(f"[b2] {arm} N={n} done")
    emit("b2_concurrency", {
        "config": {"n_values": N_VALUES, "ops_per_writer": OPS_PER_WRITER,
                   "max_retries": MAX_RETRIES, "retry_sleep_s": RETRY_SLEEP_S},
        "cells": cells,
    })


if __name__ == "__main__":
    main()
