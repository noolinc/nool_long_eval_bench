"""opencode adapter — drives `opencode run` headlessly.

Token/turn/tool counts come from the CLI's own `--format json` event stream.
Nothing is estimated: fields the CLI does not report are null. opencode
exposes no max-turns knob, so `max_turns` is accepted for contract
compatibility but not enforced (the wall-clock timeout is the only bound).

Environment isolation (mandatory, see harness/README.md): the operator's
user-level opencode configuration (~/.config/opencode: global agents,
plugins, skills) must not leak into benchmark sessions. We point
XDG_CONFIG_HOME at a throwaway directory so user-level config is excluded;
project/workspace-level .opencode config stays enabled because the nool
arm's workspace hooks are the treatment under test. Auth lives under the
data dir (~/.local/share/opencode), which is unaffected.
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path

NAME = "opencode"

# Permission surface mirrored from adapters/claude.ALLOWED_TOOLS so both
# harnesses expose agents an equivalent tool policy: file tools unrestricted,
# shell restricted to the benchmark's VCS/toolchain commands, no network
# fetching. Written as project-level config for each session and removed
# afterwards so it never enters a ticket branch.
ALLOWED_BASH = [
    "go build *", "go test *", "go vet *", "gofmt *", "git *", "nool *",
]


def _permission_config(workdir):
    cfg_dir = Path(workdir) / ".opencode"
    cfg_dir.mkdir(exist_ok=True)
    path = cfg_dir / "opencode.json"
    path.write_text(json.dumps({
        "$schema": "https://opencode.ai/config.json",
        "permission": {
            "edit": "allow",
            "webfetch": "deny",
            "bash": {p: "allow" for p in ALLOWED_BASH}
            | {"*": "ask"},
        },
    }, indent=1))
    return path


def preflight():
    v = subprocess.run(["opencode", "--version"], capture_output=True,
                       text=True, timeout=30)
    return {"adapter": NAME,
            "cli_version": (v.stdout or v.stderr).strip().splitlines()[0]}


def run(workdir, prompt_text, model, max_turns, timeout_s, transcript_path,
        env):
    # Throwaway XDG_CONFIG_HOME per call; left in the system temp dir on
    # purpose (opencode may still write there after the process exits).
    isolated_cfg = tempfile.mkdtemp(prefix="opencode_bench_cfg_")
    cmd = [
        "opencode", "run", prompt_text,
        "--model", model,
        "--format", "json",
        # opencode resolves the workspace from --dir / $PWD, not getcwd()
        # (observed 2026-08-22: with only cwd= set, sessions landed in the
        # operator's shell directory and agents wandered into the harness
        # repo). Pin both.
        "--dir", str(workdir),
    ]
    run_env = dict(env, XDG_CONFIG_HOME=isolated_cfg, PWD=str(workdir))
    perm_path = _permission_config(workdir)
    try:
        t0 = time.monotonic()
        try:
            p = subprocess.run(cmd, cwd=str(workdir), env=run_env,
                               timeout=timeout_s, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
            timed_out = False
            raw = p.stdout
            stderr_tail = p.stderr[-2000:]
            exit_code = p.returncode
        except subprocess.TimeoutExpired as e:
            timed_out = True
            raw = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) \
                else (e.stdout or "")
            stderr_tail = ""
            exit_code = None
        wall_ms = (time.monotonic() - t0) * 1000.0
    finally:
        # Never let harness config enter the ticket branch.
        try:
            perm_path.unlink()
            perm_path.parent.rmdir()
        except OSError:
            pass

    Path(transcript_path).write_text(raw)

    result = {
        "adapter": NAME, "exit_code": exit_code, "timed_out": timed_out,
        "wall_ms": round(wall_ms, 1), "stderr_tail": stderr_tail,
        "model_reported": None, "num_turns": None, "tool_calls": None,
        "tokens_in": None, "tokens_out": None,
        "cache_read_tokens": None, "cache_creation_tokens": None,
        "cost_usd": None, "is_error": None,
    }
    tool_calls = 0
    num_turns = 0
    tok_in = tok_out = cache_read = cache_write = 0
    cost = 0.0
    saw_step = False
    model_reported = None
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = ev.get("part") or {}
        if not model_reported:
            mid = part.get("modelID") or ev.get("modelID")
            if mid:
                pid = part.get("providerID") or ev.get("providerID")
                model_reported = f"{pid}/{mid}" if pid else str(mid)
        if ev.get("type") == "step_finish":
            saw_step = True
            num_turns += 1
            usage = part.get("tokens") or {}
            tok_in += usage.get("input") or 0
            tok_out += usage.get("output") or 0
            cache_read += (usage.get("cache") or {}).get("read") or 0
            cache_write += (usage.get("cache") or {}).get("write") or 0
            cost += part.get("cost") or 0.0
        elif ev.get("type") == "tool_use":
            tool_calls += 1
        elif ev.get("type") in ("error",):
            result["stderr_tail"] = (result["stderr_tail"] + "\n" +
                                     json.dumps(ev))[-2000:]
    if saw_step:
        result.update({
            "num_turns": num_turns,
            "tokens_in": tok_in,
            "tokens_out": tok_out,
            "cache_read_tokens": cache_read or None,
            "cache_creation_tokens": cache_write or None,
            "cost_usd": round(cost, 6),
        })
    result["model_reported"] = model_reported
    result["tool_calls"] = tool_calls or None
    return result
