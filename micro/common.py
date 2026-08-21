"""Shared helpers for the Track B mechanism micro-benchmarks.

Every benchmark: creates isolated workspaces under a temp dir, times with
monotonic clocks (ms), and emits one JSON result file with full provenance.
No LLM involvement anywhere in Track B.
"""

import json
import os
import platform
import shutil
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results" / "micro"

ENV = dict(os.environ, NOOL_NO_DAEMON="1", GIT_TERMINAL_PROMPT="0")


def run(cmd, cwd, check=False, timeout=300):
    """Run a command; return (exit_code, stdout+stderr, elapsed_ms)."""
    t0 = time.monotonic()
    p = subprocess.run(
        cmd, cwd=str(cwd), env=ENV, timeout=timeout,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    ms = (time.monotonic() - t0) * 1000.0
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd} failed ({p.returncode}) in {cwd}:\n{p.stdout}")
    return p.returncode, p.stdout, ms


def make_workspace(parent, name, nool=False):
    """Fresh git repo (branch `main`, fixed identity); optionally nool-tracked."""
    ws = Path(parent) / name
    ws.mkdir(parents=True)
    run(["git", "init", "-q", "-b", "main"], ws, check=True)
    run(["git", "config", "user.email", "bench@nool-benchmarks.local"], ws, check=True)
    run(["git", "config", "user.name", "Bench"], ws, check=True)
    if nool:
        code, out, _ = run(["nool", "init"], ws)
        if code != 0:
            raise RuntimeError(f"nool init failed in {ws}:\n{out}")
    return ws


def git_commit_all(ws, msg):
    run(["git", "add", "-A"], ws, check=True)
    return run(["git", "commit", "-qm", msg], ws)


def nool_land(ws, intent, paths=None, extra=None, fast=False):
    """propose --fast --solidify; returns (code, out, ms)."""
    cmd = ["nool", "propose", "--intent", intent, "--solidify", "--compact"]
    if fast:
        cmd += ["--fast"]
    if paths:
        cmd += ["--path", *paths]
    else:
        cmd += ["--all"]
    if extra:
        cmd += extra
    return run(cmd, ws)


def version_of(cmd):
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=15).stdout.strip().splitlines()[0]
    except Exception as e:  # tool absent — recorded, not fatal
        return f"unavailable: {e}"


def provenance():
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "nool_version": version_of(["nool", "--version"]),
        "git_version": version_of(["git", "--version"]),
        "go_version": version_of(["go", "version"]),
        "python_version": platform.python_version(),
        "os_version": platform.mac_ver()[0] or platform.release(),
        "execution": "local (containerization deferred; see spec §8)",
    }


def summarize_ms(samples):
    if not samples:
        return None
    s = sorted(samples)
    return {
        "n": len(s),
        "median_ms": round(statistics.median(s), 2),
        "p10_ms": round(s[max(0, int(len(s) * 0.10) - 1)], 2) if len(s) >= 3 else None,
        "p90_ms": round(s[min(len(s) - 1, int(len(s) * 0.90))], 2) if len(s) >= 3 else None,
        "min_ms": round(s[0], 2),
        "max_ms": round(s[-1], 2),
    }


def emit(name, payload):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"benchmark": name, "provenance": provenance(), **payload}
    out = RESULTS_DIR / f"{name}.json"
    out.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"[{name}] wrote {out}")
    return out


class TempRoot:
    """Context manager for the benchmark's scratch parent directory."""

    def __init__(self, tag):
        self.tag = tag

    def __enter__(self):
        self.path = Path(tempfile.mkdtemp(prefix=f"noolbench_{self.tag}_"))
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)
