#!/usr/bin/env bash
# Nool Passive Agent Hook — Claude Code
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOOL_DIR="$(cd "$HOOK_DIR/../.." && pwd)"
PROJECT_ROOT="$(cd "$NOOL_DIR/.." && pwd)"
NOOL_LOG="$NOOL_DIR/session_transcript.jsonl"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
PAYLOAD="$(cat)"

if command -v jq >/dev/null 2>&1; then
    echo "$PAYLOAD" | jq -c --arg ts "$TIMESTAMP" '. + {_nool_captured_at: $ts}' >> "$NOOL_LOG" 2>/dev/null \
        || printf '{"_nool_captured_at":"%s","raw":%s}\n' "$TIMESTAMP" "$(printf '%s' "$PAYLOAD" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')" >> "$NOOL_LOG"
else
    printf '{"_nool_captured_at":"%s","raw_payload":%s}\n' "$TIMESTAMP" "$PAYLOAD" >> "$NOOL_LOG" 2>/dev/null || true
fi

# On session end, queue (never solidify) one proposal referencing the
# accumulated transcript for the operator to review — a single artifact per
# session rather than one per tool call.
EVENT_NAME="$(echo "$PAYLOAD" | jq -r '.hook_event_name // empty' 2>/dev/null)"
if [ "$EVENT_NAME" = "Stop" ] && command -v nool >/dev/null 2>&1; then
    # Propose from the project root, not the session's working directory.
    # Claude Code runs hooks with whatever cwd the session started in, which
    # is often not the project root -- a git worktree, or any `-C` target.
    # Proposing from there would address a different ledger, or create a
    # stray one where no project is tracked.
    (cd "$PROJECT_ROOT" && \
        nool propose --intent "Claude Code session transcript ($TIMESTAMP)" \
            --path "$NOOL_LOG" --kind doc --quiet) 2>/dev/null || true
fi

exit 0
