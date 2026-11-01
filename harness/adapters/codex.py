"""Codex CLI adapter using its headless JSONL event stream.

User Codex config, rules and instruction files are excluded. Authentication is
copied from the configured CODEX_HOME into a per-session private home. Usage and
cost are recorded only when the CLI emits native values.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

NAME = "codex"


def _private_codex_home(env):
    source = Path(env.get("CODEX_HOME", Path.home() / ".codex"))
    auth = source / "auth.json"
    auth_data = json.loads(auth.read_text()) if auth.is_file() else {}
    auth_mode = auth_data.get("auth_mode")
    api_key = env.get("CODEX_API_KEY") or env.get("OPENAI_API_KEY")
    if not auth.is_file() and not api_key:
        raise RuntimeError("Codex authentication file is not available in CODEX_HOME")
    destination = Path(tempfile.mkdtemp(prefix="codex_bench_home_"))
    isolated_env = dict(env, HOME=str(destination), CODEX_HOME=str(destination))
    if auth.is_file() and auth_mode == "chatgpt":
        # Honor the active ChatGPT login even when the parent shell exports an
        # API key. Otherwise that unrelated key silently overrides the login.
        isolated_env.pop("OPENAI_API_KEY", None)
        isolated_env.pop("CODEX_API_KEY", None)
        shutil.copy2(auth, destination / "auth.json")
    elif api_key:
        login = subprocess.run(["codex", "login", "--with-api-key"], env=isolated_env,
                               input=api_key, capture_output=True, text=True,
                               timeout=30)
        if login.returncode:
            shutil.rmtree(destination, ignore_errors=True)
            raise RuntimeError("Codex API-key login failed in the private benchmark home")
    elif auth.is_file():
        shutil.copy2(auth, destination / "auth.json")
    return destination


def preflight():
    v = subprocess.run(["codex", "--version"], capture_output=True, text=True,
                       timeout=30)
    source = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return {"adapter": NAME, "cli_version": (v.stdout or v.stderr).strip(),
            "auth_available": (source / "auth.json").is_file(),
            "user_config_isolated": True}


def run(workdir, prompt_text, model, max_turns, timeout_s, transcript_path, env):
    codex_home = _private_codex_home(env)
    run_env = dict(env, HOME=str(codex_home), CODEX_HOME=str(codex_home))
    cmd = ["codex", "exec", "--json", "--ephemeral", "--model", model,
           "--sandbox", "workspace-write",
           "--ignore-user-config", "--ignore-rules",
           "--skip-git-repo-check", "--cd", str(workdir), prompt_text]
    started = time.monotonic()
    try:
        try:
            p = subprocess.run(cmd, cwd=str(workdir), env=run_env, timeout=timeout_s,
                               capture_output=True, text=True)
            raw, stderr, code, timed_out = p.stdout, p.stderr[-2000:], p.returncode, False
        except subprocess.TimeoutExpired as exc:
            def string(v):
                return v.decode(errors="replace") if isinstance(v, bytes) else v or ""
            raw, stderr, code, timed_out = string(exc.stdout), string(exc.stderr)[-2000:], None, True
        result = {"adapter": NAME, "exit_code": code, "timed_out": timed_out,
                  "wall_ms": round((time.monotonic() - started) * 1000, 1),
                  "stderr_tail": stderr, "model_reported": None,
                  "num_turns": None, "tool_calls": None, "tokens_in": None,
                  "tokens_out": None, "cache_read_tokens": None,
                  "cache_creation_tokens": None, "cost_usd": None, "is_error": None}
        turns = tools = 0
        latest_usage = None
        for line in raw.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            # `codex exec --json` emits event fields at the top level. Keep
            # compatibility with wrapped payloads too, but do not discard the
            # native JSONL fields (usage, item, thread_id, etc.).
            payload = ev.get("payload") or ev
            typ = ev.get("type") or payload.get("type")
            if typ in ("turn.started", "turn.completed"):
                turns += typ == "turn.completed"
                model_value = payload.get("model") or payload.get("model_id")
                if model_value:
                    result["model_reported"] = model_value
            elif typ == "thread.started":
                result["thread_id"] = payload.get("thread_id")
            elif typ == "item.completed":
                item = payload.get("item") or {}
                if item.get("type") in ("command_execution", "file_change", "mcp_tool_call", "web_search"):
                    tools += 1
            elif typ in ("token_count", "turn.completed"):
                info = payload.get("info") or {}
                latest_usage = info.get("total_token_usage") or payload.get("usage") or latest_usage
                if "cost_usd" in payload:
                    result["cost_usd"] = payload["cost_usd"]
        if turns:
            result["num_turns"] = turns
        if tools:
            result["tool_calls"] = tools
        if latest_usage:
            result["tokens_in"] = latest_usage.get("input_tokens")
            result["tokens_out"] = latest_usage.get("output_tokens")
            result["cache_read_tokens"] = latest_usage.get("cached_input_tokens")
            result["cache_creation_tokens"] = latest_usage.get("cache_write_input_tokens")
        result["is_error"] = code not in (None, 0)
        Path(transcript_path).write_text(raw)
        return result
    finally:
        shutil.rmtree(codex_home, ignore_errors=True)
