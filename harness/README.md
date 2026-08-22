# Track C harness

Drives coding-agent CLIs headlessly over `tasks/` in a 2×2 design
(VCS: git|nool × mode: single|multi). See the design spec (§3) for the
experimental controls; this file documents the adapter contract.

## Running

```bash
python3 run_experiment.py --harness claude --model <pinned-model-id> \
    --tasks redux_go --cells all --reps 5
```

One pinned model id is used for every cell of an experiment; the adapter
records the model the CLI actually reports (`model_reported`) so drift is
detectable. Results append to `results/trackc/runs.jsonl` (committed);
full transcripts go to `results/trackc/transcripts/` (gitignored, local).

## Adapter contract

An adapter is a module in `adapters/` exposing:

```python
NAME: str
def preflight() -> dict          # CLI version / auth sanity; recorded per run
def run(workdir, prompt_text, model, max_turns, timeout_s,
        transcript_path, env) -> dict
```

`run()` must be blocking and headless, write the raw transcript to
`transcript_path`, and return a dict with at least: `exit_code`,
`timed_out`, `wall_ms`, `model_reported`, `num_turns`, `tool_calls`,
`tokens_in`, `tokens_out`, `cost_usd`. **Fields the CLI does not expose are
`None` — estimating is banned.** The tool allowlist must be identical across
arms (the workspace, not the tool set, is the manipulated variable).

**Environment isolation is mandatory.** The operator's user-level agent
configuration (plugins, skills, personal hooks, global memory files) must be
excluded from benchmark sessions; project/workspace-level configuration must
stay enabled, because the nool arm's workspace hooks are the treatment under
test. For Claude Code this is `--setting-sources project,local`. An early
batch without this was invalidated — see
`results/trackc/invalidated_2026-08-20_user-config-contamination/NOTE.md`.
Any new adapter must document the equivalent isolation mechanism for its CLI
before its data is analyzed.

Implemented: `claude` (Claude Code CLI, stream-json accounting) and
`opencode` (opencode CLI ≥1.18, `run --format json` event accounting).
To add gemini/codex/pi: implement the same contract with that CLI's
headless mode and native usage accounting, then register it in
`run_experiment.py:ADAPTERS`.

**opencode isolation mechanism:** user-level configuration is excluded by
pointing `XDG_CONFIG_HOME` at a throwaway directory for each session
(global agents/plugins/skills live under `~/.config/opencode`; auth lives
under the data dir and is unaffected). Project/workspace-level `.opencode`
config stays enabled. Two opencode-specific correctness notes recorded
2026-08-22: (a) opencode resolves its workspace from `--dir`/`$PWD` rather
than the process cwd — the adapter pins both to the ticket worktree;
(b) `max_turns` has no CLI equivalent, so the wall-clock timeout is the
only turn bound and `num_turns` is reported from observed step events.

## Multi-agent protocol

Sub-agents run in isolated git worktrees on branches `agent_1..K` with an
identical, task-authored decomposition (`spec_parts/`) in both arms, and
commit with git; the arms differ only at integration (`git merge` vs
`nool merge`, fixed order, no conflict resolution). Single-agent cells
exercise the full in-workspace workflow difference instead (nool init
installs its agent hooks there). Scoring copies `hidden_tests/` in only
after the agents are done: `go build ./...` then `go test ./...`.
