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
        # Create minimal go.mod so nool's integrity driver can locate project root
        # for Go projects (required in 6.14.x; absent in benchmarks' temp repos).
        go_mod = ws / "go.mod"
        if not go_mod.exists():
            go_mod.write_text("module bench\ngo 1.21\n")
    return ws


def git_commit_all(ws, msg):
    run(["git", "add", "-A"], ws, check=True)
    return run(["git", "commit", "-qm", msg], ws)


def nool_land(ws, intent, paths=None, extra=None, fast=False):
    """propose --solidify in an EXPLICIT validation mode; returns (code, out, ms).

    The mode is always passed on the command line rather than left to the CLI
    default, so that what each cell measures is a property of this file and
    not of whichever nool build happens to be installed. The default has been
    full governance at every version this suite has measured -- b4's committed
    results reject a test-breaking change on the no-flag path from 6.14.1
    through 7.2.0, while the explicit `--fast` cell accepts it -- so this is a
    no-op today and is verified as one (b4 outcomes are byte-identical across
    the change). It is defensive, not a bug fix: the default is undocumented
    in the sense that nothing pins it, and a silent change to it would
    otherwise rewrite what "governed" means here without touching this repo.
    `fast=True` is the deferred-validation path; `fast=False` is the governed
    path.
    """
    cmd = ["nool", "propose", "--intent", intent, "--solidify", "--compact"]
    cmd += ["--fast"] if fast else ["--full"]
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


def load_average():
    """1/5/15-minute load, and cores, so a run on a busy box is self-evident.

    The git arm is the control: if the machine is loaded, *both* arms inflate
    and the absolute medians stop being comparable across runs. A 7.1.3 re-run
    during a concurrent `rustc` build (load 119 on 10 cores) moved git's own
    commit latency 22ms -> 48ms, which no Nool version could have caused.
    """
    try:
        one, five, fifteen = os.getloadavg()
        cores = os.cpu_count() or 1
        return {"load_1m": round(one, 2), "load_5m": round(five, 2),
                "load_15m": round(fifteen, 2), "cpu_count": cores,
                "load_per_core_1m": round(one / cores, 2),
                "quiet": (one / cores) < 1.5}
    except Exception as e:
        return {"error": str(e), "quiet": None}


def provenance():
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "system_load": load_average(),
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
    prov = provenance()
    load = prov.get("system_load", {})
    if load.get("quiet") is False:
        print(f"[{name}] WARNING: machine is not quiet "
              f"(load {load.get('load_1m')} on {load.get('cpu_count')} cores = "
              f"{load.get('load_per_core_1m')}/core). Absolute medians in this "
              f"result are inflated in BOTH arms and are not comparable with "
              f"results collected on an idle machine. Re-run when quiet before "
              f"citing these numbers.")
    payload = {"benchmark": name, "provenance": prov, **payload}
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

# A bare `git commit` does almost no work, while `nool propose --solidify`
# parses syntax, registers entities, evaluates blast radius and runs the policy
# gate. Comparing the two overstates Nool's overhead. These hooks give git a
# like-for-like baseline: the "fast" stack mirrors Nool's fast path (syntax
# precheck + policy gate), the "full" stack adds a toolchain check standing in
# for reification. Neither signs -- no GPG key is assumed -- so both git arms
# still do strictly less than Nool, and the ratios remain an upper bound.
PRECOMMIT_FAST = r"""#!/bin/sh
set -e
changed=$(git diff --cached --name-only --diff-filter=ACM | grep '\.go$' || true)
[ -z "$changed" ] && exit 0
# syntax/AST precheck
unformatted=$(gofmt -l $changed || true)
[ -n "$unformatted" ] && { echo "gofmt: $unformatted"; exit 1; }
# policy gate: forbidden paths + change-width guard
for f in $changed; do
  case "$f" in secrets/*|*.pem) echo "forbidden path: $f"; exit 1;; esac
done
n=$(printf '%s\n' $changed | wc -l | tr -d ' ')
[ "$n" -gt 500 ] && { echo "change too wide: $n files"; exit 1; }
exit 0
"""

PRECOMMIT_FULL = PRECOMMIT_FAST.replace(
    "exit 0\n", "go vet ./... >/dev/null 2>&1 || true\nexit 0\n")


def install_precommit(ws, stack="fast"):
    """Install a pre-commit hook so the git arm does comparable work."""
    hook = Path(ws) / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(PRECOMMIT_FAST if stack == "fast" else PRECOMMIT_FULL)
    hook.chmod(0o755)
    return hook
