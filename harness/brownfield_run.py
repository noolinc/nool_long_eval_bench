#!/usr/bin/env python3
"""Track G brownfield-conformance probe runner.

Question under test (the angle the rest of the suite does not cover): does
nool's semantic layer — knowledge ledger, task system, workspace hooks —
help a coding agent DISCOVER and RESPECT a brownfield repository's
architectural decisions, and can an architect encode structure ONCE in
nool instead of repeating it in every prompt?

Cells (N=1 per cell; this is a pilot, labeled directional everywhere):
  git_fat    plain git. Fat prompt: full spec + explicit instruction to
             follow DECISIONS.md and existing patterns. The strongest
             baseline prompt engineering can offer.
  git_thin   plain git. Thin prompt: one line pointing at TICKETS.md.
             What happens when nobody repeats the rules.
  nool_thin  nool workspace (nool init, decisions seeded into the
             knowledge ledger, ticket registered on the task board).
             Identical thin prompt to git_thin.
  handoff_*  phase A runs with a short wall-clock cap and must land
             whatever exists ("routinely interrupted agent" scenario);
             a FRESH agent then gets only the recovery line. Tests
             session-agnostic handoff via recorded state.

Scoring: tasks/brownfield_service/score.py — hidden behavioral tests +
static conformance checks against DECISIONS.md's D1-D5. Orientation cost
comes from the adapter's own accounting (turns, tokens, tool calls).

Zero-cost execution: defaults to the opencode free-tier model used by the
fleet harness; any adapter/model pair works via flags.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from adapters import opencode as opencode_adapter  # noqa: E402


def _permissive_permission_config(workdir):
    """Track G deviation from adapters/opencode.ALLOWED_BASH, disclosed:
    the fleet allowlist ("go build *", "git *", ...) rejects compound
    shell commands (`ls && git log`), which headless sessions experience
    as instant permission rejections — pilots showed agents giving up
    after 1-3 turns without doing any work. Exploration IS the treatment
    here, so bash is fully allowed for every cell identically. Sessions
    run in throwaway temp worktrees with no credentials.
    """
    cfg_dir = Path(workdir) / ".opencode"
    cfg_dir.mkdir(exist_ok=True)
    path = cfg_dir / "opencode.json"
    path.write_text(json.dumps({
        "$schema": "https://opencode.ai/config.json",
        "permission": {
            "edit": "allow", "webfetch": "deny", "bash": {"*": "allow"},
        },
    }, indent=1))
    return path


opencode_adapter._permission_config = _permissive_permission_config

REPO = HERE.parent
TASK = REPO / "tasks" / "brownfield_service"
RESULTS = REPO / "results" / "trackg"
TRANSCRIPTS = RESULTS / "transcripts"

MODEL_DEFAULT = "opencode/x-preview-f-free"

TICKETS_MD = """# Tickets

## GIFT-101: batch gifting endpoint

Add `POST /gift` to the HTTP API.

Request:

```json
{"recipients": [{"email": "alice@example.com", "dollars": 19.99},
                {"email": "bob@example.com",   "dollars": 3.00}]}
```

Credit each recipient's account by their dollar amount. Unknown email
addresses must not crash the server. Respond with JSON.
"""

PROMPT_FAT = """You are working in the giftshop repository.

Ticket GIFT-101 (full text also in TICKETS.md): add POST /gift accepting
JSON {"recipients":[{"email":"...","dollars":19.99}, ...]}. Credit each
recipient's account by their dollar amount; unknown emails must not crash
the server; respond with JSON.

Before writing code, read DECISIONS.md and skim recent history — this repo
has strict conventions (layering, money handling, error handling) that are
enforced in review. Implement, verify with go build ./... && go vet ./...
&& go test ./..., then commit your work.
"""

PROMPT_THIN = """Implement ticket GIFT-101 (see TICKETS.md). Verify your change
builds, then land your work with the repository's workflow.
"""

PROMPT_RECOVERY = """A previous engineer was interrupted partway through
implementing ticket GIFT-101 (see TICKETS.md). Recover their progress from
this repository's history and workflow, finish the work correctly, verify
it builds, and land it.
"""

DECISION_FINDINGS = [
    "D1 layering: dependencies flow api -> service -> store; handlers "
    "never import or touch internal/store.",
    "D2 money is integer cents; outside dollar values convert ONLY via "
    "service.ParseDollarsToCents (rounds); naive int() truncation caused "
    "incident #12.",
    "D3 errors carry cause: wrap with %w so callers match "
    "store.ErrNotFound; missing user => client 4xx, never 500/panic.",
    "D4 operations live on *service.Shop as methods; business logic is "
    "never re-implemented inside handlers.",
    "D5 emails compare normalized via service.NormalizeEmail (lowercase, "
    "trimmed), everywhere.",
]


def sh(cmd, cwd, timeout=120):
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def build_base(parent: Path) -> Path:
    sys.path.insert(0, str(TASK))
    import build_repo
    base = parent / "_base"
    build_repo.build(base)
    (base / "TICKETS.md").write_text(TICKETS_MD)
    sh(["git", "add", "-A"], base)
    sh(["git", "commit", "-qm", "tickets: GIFT-101"], base)
    return base


def fresh_ws(base: Path, parent: Path, name: str) -> Path:
    ws = parent / name
    shutil.copytree(base, ws)
    return ws


def import_nool(ws: Path):
    """Authentic brownfield adoption flow (the treatment).

    Step 1 — `nool init` on the existing git repo: imports commit history
    as knots, discovers feature boundaries (`discover features` + lift),
    builds the entity graph, recovers architecture. This is the whole
    point under test: the graph must come from the repo itself, not from
    anything we hand it.

    Step 2 — decision audit: a team adopting nool on a mature repo
    extracts its architectural decisions from history/docs into the
    ledger once, exactly as we do here with D1-D5 (recovered from
    DECISIONS.md + commit messages that ship with the corpus). Both arms
    have the identical DECISIONS.md file; the ledger is nool's native
    place to put the same knowledge.

    Step 3 — ticket registered on the task board (thin-prompt support).
    """
    code, out = sh(["nool", "init"], ws, timeout=600)
    if code != 0:
        raise RuntimeError(f"nool init failed: {out}")
    # Hard-fail unless the import actually built the semantic graph
    # (feature identities minted for every package).
    code, ctx = sh(["nool", "query", "context", "internal.service"], ws,
                   timeout=120)
    if code != 0 or "feature:internal.service" not in ctx:
        raise RuntimeError(
            f"no feature graph after init — import did not lift:\n{ctx}")
    for i, d in enumerate(DECISION_FINDINGS, 1):
        code, out = sh(["nool", "learn", "--about", "giftshop-architecture",
                        "--kind", "finding", "--content",
                        f"D{i} (recovered from history): {d}"],
                       ws, timeout=120)
        if code != 0:
            raise RuntimeError(f"nool learn failed: {out}\n{d}")
    code, out = sh(["nool", "task", "create", "--name", "GIFT-101",
                    "--desc", "POST /gift: credit dollar amounts to users "
                    "by email; unknown emails handled gracefully",
                    "--acceptance",
                    "POST /gift credits each recipient exactly "
                    "(rounded cents); unknown email yields client error"],
                   ws, timeout=120)
    if code != 0:
        raise RuntimeError(f"task create failed: {out}")


def changed_files(ws: Path, start: str):
    code, out = sh(["git", "diff", "--name-only", start, "HEAD"], ws)
    return sorted(l for l in out.splitlines() if l.strip())


def run_cell(cell, base, parent, model, timeout_s, phase_a_timeout=None):
    sys.path.insert(0, str(TASK))
    import score as scorer

    run_id = f"trackg_{cell}_{uuid.uuid4().hex[:8]}"
    ws = fresh_ws(base, parent, f"ws_{cell}")
    _, start_sha = sh(["git", "rev-parse", "HEAD"], ws)
    start_sha = start_sha.strip()
    if cell.startswith("nool") or cell.startswith("handoff_nool"):
        import_nool(ws)
        # The ledger is VCS-internal state; keep it out of history even if
        # an agent (or the harness WIP landing) runs `git add -A`.
        gi = ws / ".gitignore"
        gi.write_text((gi.read_text() if gi.exists() else "") + ".nool/\n")

    if cell == "git_fat":
        prompt, ptag = PROMPT_FAT, "fat"
    else:
        prompt, ptag = PROMPT_THIN, "thin"
    prompts_run = []

    def agent(text, tmo, tag):
        tp = TRANSCRIPTS / f"{run_id}_{tag}.jsonl"
        TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
        res = opencode_adapter.run(ws, text, model, max_turns=40,
                                   timeout_s=tmo, transcript_path=tp,
                                   env=os.environ.copy())
        prompts_run.append({"tag": tag,
                            "prompt_sha": sha(text),
                            "prompt_bytes": len(text)})
        # Land whatever exists (fleet precedent): interrupted agents leave
        # uncommitted trees; scoring judges final state. VCS-internal state
        # (.nool ledger) never enters history.
        sh(["git", "add", "-A"], ws)
        sh(["git", "reset", "-q", "--", ".nool"], ws)
        sh(["git", "commit", "-qm",
            f"{tag}: work-in-progress landing by harness"], ws)
        return res

    phases = {}
    if cell.startswith("handoff"):
        phases["A"] = agent(prompt, phase_a_timeout or 150,
                            "phaseA")
        phases["B"] = agent(PROMPT_RECOVERY, timeout_s, "phaseB")
    else:
        phases["single"] = agent(prompt, timeout_s, "main")

    rec = {
        "run_id": run_id, "cell": cell, "model": model,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "prompts": prompts_run,
        "phases": {k: {kk: vv for kk, vv in v.items()
                       if kk != "stderr_tail"} for k, v in phases.items()},
        "changed_files": changed_files(ws, start_sha),
        # Source snapshot: the workspaces are throwaway; the record must
        # carry the evidence (final production sources) for audit.
        "sources": {
            str(p.relative_to(ws)): p.read_text()
            for p in list((ws / "internal").rglob("*.go"))
            if not p.name.endswith("_test.go")
        },
        "score": scorer.score(ws),
    }
    return ws, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="git_fat,git_thin,nool_thin,"
                    "handoff_git,handoff_nool")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--timeout", type=int, default=600,
                    help="per-phase agent wall-clock budget (s)")
    ap.add_argument("--phase-a-timeout", type=int, default=150,
                    help="interrupted-agent cap for handoff cells (s)")
    args = ap.parse_args()

    parent = Path(tempfile.mkdtemp(prefix="trackg_"))
    base = build_base(parent)
    results_path = RESULTS / "runs.jsonl"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        for cell in args.cells.split(","):
            print(f"[trackg] running cell {cell}", flush=True)
            _, rec = run_cell(cell, base, parent, args.model,
                              args.timeout, args.phase_a_timeout)
            rec["preflight"] = {"adapter": "opencode"}
            with open(results_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            s = rec["score"]
            print(f"[trackg] {cell}: violations="
                  f"{','.join(s['conformance_violations']) or 'NONE'} "
                  f"behavior={sum(s['behavior'].values())}/"
                  f"{len(s['behavior'])}", flush=True)
    finally:
        shutil.rmtree(parent, ignore_errors=True)


if __name__ == "__main__":
    main()
