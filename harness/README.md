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

Implemented: `claude` (Claude Code CLI, stream-json accounting).
To add gemini/codex/pi: implement the same contract with that CLI's
headless mode and native usage accounting, then register it in
`run_experiment.py:ADAPTERS`.

## Multi-agent protocol

Sub-agents run in isolated git worktrees on branches `agent_1..K` with an
identical, task-authored decomposition (`spec_parts/`) in both arms, and
commit with git; the arms differ only at integration (`git merge` vs
`nool merge`, fixed order, no conflict resolution). Single-agent cells
exercise the full in-workspace workflow difference instead (nool init
installs its agent hooks there). Scoring copies `hidden_tests/` in only
after the agents are done: `go build ./...` then `go test ./...`.
