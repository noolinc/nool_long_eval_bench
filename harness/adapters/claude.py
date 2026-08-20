"""Claude Code adapter — drives `claude -p` headlessly.

Token/turn/tool counts come from the CLI's own stream-json accounting.
Nothing is estimated: fields the CLI does not report are null.
"""

import json
import subprocess
import time
from pathlib import Path

NAME = "claude"

# Identical across all arms and cells; the workspace, not the tool set, is
# the manipulated variable. Both VCS CLIs are allowed everywhere.
ALLOWED_TOOLS = ",".join([
    "Read", "Write", "Edit", "Glob", "Grep", "LS", "TodoWrite",
    "Bash(go build:*)", "Bash(go test:*)", "Bash(go vet:*)", "Bash(gofmt:*)",
    "Bash(git:*)", "Bash(nool:*)",
])


def preflight():
    v = subprocess.run(["claude", "--version"], capture_output=True, text=True,
                       timeout=30)
    return {"adapter": NAME, "cli_version": v.stdout.strip()}


def run(workdir, prompt_text, model, max_turns, timeout_s, transcript_path, env):
    cmd = [
        "claude", "-p", prompt_text,
        "--model", model,
        "--output-format", "stream-json", "--verbose",
        "--max-turns", str(max_turns),
        "--allowedTools", ALLOWED_TOOLS,
        # Environment isolation: user-level settings (plugins, skills, personal
        # hooks, user CLAUDE.md) must not leak into benchmark sessions — they
        # contaminated pilot runs (an agent invoked a user-installed skill that
        # told it to await human approval, so it never wrote code). Project
        # settings stay enabled: the nool arm's workspace hooks ARE the
        # treatment under test.
        "--setting-sources", "project,local",
    ]
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=str(workdir), env=env, timeout=timeout_s,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True)
        timed_out = False
        raw = p.stdout
        stderr_tail = p.stderr[-2000:]
        exit_code = p.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        raw = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr_tail = ""
        exit_code = None
    wall_ms = (time.monotonic() - t0) * 1000.0

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
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            result["model_reported"] = ev.get("model")
        elif ev.get("type") == "assistant":
            content = (ev.get("message") or {}).get("content") or []
            tool_calls += sum(1 for c in content
                              if isinstance(c, dict) and c.get("type") == "tool_use")
        elif ev.get("type") == "result":
            usage = ev.get("usage") or {}
            result.update({
                "num_turns": ev.get("num_turns"),
                "cost_usd": ev.get("total_cost_usd"),
                "is_error": ev.get("is_error"),
                "tokens_in": usage.get("input_tokens"),
                "tokens_out": usage.get("output_tokens"),
                "cache_read_tokens": usage.get("cache_read_input_tokens"),
                "cache_creation_tokens": usage.get("cache_creation_input_tokens"),
            })
    result["tool_calls"] = tool_calls or None
    return result
