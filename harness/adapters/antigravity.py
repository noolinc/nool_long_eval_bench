"""Antigravity (agy) adapter — drives `agy -p` headlessly.

Drop-in replacement for claude.py. The agy CLI stream-json format uses
`event` keys instead of `type`, so this adapter translates accordingly.

Runs are labeled with adapter="antigravity" and arm suffix "_agy" so they
sit alongside (not replacing) the primary claude-sonnet-5 comparison series.
"""

# Translate claude-style model IDs → agy display names
MODEL_MAP = {
    "claude-sonnet-5":        "Claude Sonnet 4.6 (Thinking)",
    "claude-sonnet-4-5":      "Claude Sonnet 4.6 (Thinking)",
    "claude-opus-5":          "Claude Opus 4.6 (Thinking)",
    "gemini-2.5-pro":         "Gemini 3.1 Pro (High)",
    "gemini-2.5-flash":       "Gemini 3.7 Flash (High)",
    "gemini-3.7-flash":       "Gemini 3.7 Flash (Medium)",
    "gemini-3.7-flash-medium": "Gemini 3.7 Flash (Medium)",
    "gemini-3.7-flash-high":  "Gemini 3.7 Flash (High)",
    "gemini-3.6-flash":       "Gemini 3.6 Flash (High)",
    "gemini-3.6-flash-high":  "Gemini 3.6 Flash (High)",
}

import json
import os
import subprocess
import time
from pathlib import Path

NAME = "antigravity"
AGY = "/Users/arunbalakrishnan/.local/bin/agy"

# Mirror the same tool allowlist as claude.py for a fair comparison.
# agy uses its own tool names so we keep this for logging/documentation only;
# tool restrictions are not yet supported via CLI flag in agy 1.1.x.
ALLOWED_TOOLS = ",".join([
    "Read", "Write", "Edit", "Glob", "Grep", "LS",
    "Bash(go build:*)", "Bash(go test:*)", "Bash(go vet:*)", "Bash(gofmt:*)",
    "Bash(git:*)", "Bash(nool:*)",
])


def preflight():
    v = subprocess.run(
        [AGY, "--version"], capture_output=True, text=True, timeout=30
    )
    return {"adapter": NAME, "cli_version": f"agy/{v.stdout.strip()}"}


def run(workdir, prompt_text, model, max_turns, timeout_s, transcript_path, env):
    # Inherit PATH so agy can find go, git, nool
    run_env = dict(os.environ)
    if env:
        run_env.update(env)

    # Translate model alias → agy display name
    agy_model = MODEL_MAP.get(model, model)

    cmd = [
        AGY, "-p", prompt_text,
        "--output-format", "stream-json",
        "--model", agy_model,
        "--dangerously-skip-permissions",
    ]

    t0 = time.monotonic()
    try:
        p = subprocess.run(
            cmd, cwd=str(workdir), env=run_env, timeout=timeout_s,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
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

    # Parse agy stream-json (event-based) into result fields
    result = {
        "adapter": NAME, "exit_code": exit_code, "timed_out": timed_out,
        "wall_ms": round(wall_ms, 1), "stderr_tail": stderr_tail,
        "model_reported": model, "num_turns": None, "tool_calls": None,
        "tokens_in": None, "tokens_out": None,
        "cache_read_tokens": None, "cache_creation_tokens": None,
        "cost_usd": 0.0, "is_error": None,
    }
    tool_calls = 0
    for line in raw.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = ev.get("event", "")
        if event == "init":
            pass  # model is in --model flag; agy doesn't echo it here
        elif event == "step_update":
            su = ev.get("step_update", {})
            if su.get("step_type") == "tool_use":
                tool_calls += 1
        elif event == "result":
            r = ev.get("result", {})
            usage = r.get("usage", {})
            result.update({
                "num_turns": r.get("num_turns"),
                "is_error": r.get("status") != "SUCCESS",
                "tokens_in": usage.get("input_tokens"),
                "tokens_out": usage.get("output_tokens"),
                "cache_read_tokens": usage.get("cache_read_tokens"),
                # agy does not report cost; set to 0.0 (labeled separately)
                "cost_usd": 0.0,
            })
    result["tool_calls"] = tool_calls or None
    return result
