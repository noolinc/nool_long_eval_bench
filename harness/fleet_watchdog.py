#!/usr/bin/env python3
"""RAM-watchdog wrapper for the Track D concurrency ladder (design spec,
scale-up 2). Runs one fleet_run.py invocation (one arm, one rep) per call,
sampling free memory every 3s; aborts (kills the whole process group) if
free memory stays below --min-free-pct on two consecutive samples.

An aborted run writes no fleet_runs.jsonl record (fleet_run.py only appends
on completion) — it is reported here as an infrastructure limit, never as
an arm outcome, per the pre-registered decision rule.

macOS-only (parses `vm_stat`); matches the 8%-threshold / two-consecutive-
sample protocol described in the design spec's scale-up 2 section.
"""
import argparse
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGE_RE = re.compile(r"^(Pages [a-z ]+):\s+(\d+)\.$", re.MULTILINE)


def free_pct():
    out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=10).stdout
    pages = {k.strip(): int(v) for k, v in PAGE_RE.findall(out)}
    total_bytes = int(subprocess.run(["sysctl", "-n", "hw.memsize"],
                                      capture_output=True, text=True, timeout=10).stdout.strip())
    page_size = 16384
    total_pages = total_bytes / page_size
    return 100.0 * pages.get("Pages free", 0) / total_pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["git_fleet", "nool_fleet"])
    ap.add_argument("--workers", type=int, required=True)
    ap.add_argument("--tickets", default="tickets.json")
    ap.add_argument("--model", required=True)
    ap.add_argument("--min-free-pct", type=float, default=8.0)
    ap.add_argument("--sample-s", type=float, default=3.0)
    args = ap.parse_args()

    cmd = [sys.executable, str(REPO / "harness" / "fleet_run.py"),
           "--model", args.model, "--arms", args.arm,
           "--workers", str(args.workers), "--tickets", args.tickets, "--reps", "1"]

    aborted = threading.Event()
    min_free = [100.0]

    proc = subprocess.Popen(cmd, cwd=str(REPO), start_new_session=True)

    def watch():
        below = 0
        while proc.poll() is None:
            pct = free_pct()
            min_free[0] = min(min_free[0], pct)
            if pct < args.min_free_pct:
                below += 1
                print(f"[watchdog] free={pct:.1f}% below {args.min_free_pct}% "
                      f"({below}/2 consecutive)", flush=True)
                if below >= 2:
                    print(f"[watchdog] ABORT: killing process group for "
                          f"{args.arm} (min free observed {min_free[0]:.1f}%)", flush=True)
                    aborted.set()
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    return
            else:
                below = 0
            time.sleep(args.sample_s)

    t = threading.Thread(target=watch, daemon=True)
    t.start()
    proc.wait()
    t.join(timeout=5)

    print(f"[watchdog] min free memory observed this run: {min_free[0]:.1f}%", flush=True)
    if aborted.is_set():
        print(f"[watchdog] {args.arm} CENSORED by watchdog — infrastructure limit, "
              f"not an arm outcome. No fleet_runs.jsonl record written.", flush=True)
        sys.exit(97)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
