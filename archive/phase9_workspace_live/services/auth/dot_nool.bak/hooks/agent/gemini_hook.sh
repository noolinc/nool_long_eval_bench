#!/usr/bin/env bash
# Nool Passive Agent Hook — Gemini
# Best-effort transcript capture: appends whatever arguments the caller was
# configured to pass. Not auto-registered with Gemini's own hook/config
# system (unverified schema) — wire it in manually if you use one.
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOOL_LOG="$HOOK_DIR/../../session_transcript.log"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "[$TIMESTAMP] [GEMINI] $@" >> "$NOOL_LOG" 2>/dev/null || true
exit 0
