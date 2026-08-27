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

## Fleet protocol

`fleet_run.py` records two acceptance values for every ticket. `acceptance`
is the existing end-state result: its hidden test on final `main`.
`acceptance_conditional` runs that same test at the exact commit where the
ticket landed; `null` means the ticket never landed. The second metric is the
score-attribution measure: a later poisoned merge cannot turn one event into
many ticket failures.

The `git_retry` arm is the ordinary git baseline plus exactly one automated
conflict recovery pass. It first rebases the existing ticket branch on
current `main`; if that conflicts, it starts one fresh agent attempt from
current `main` and integrates it once. Further conflicts are losses. Its
retry facts and any second agent cost are kept in the run record.

`git_competitive` is the v4 primary control: it combines footprint scheduling,
the CI/secret-gated queue, and that same single recovery pass. Under noisy
footprints, missed overlaps can still collide and exercise recovery. This is
the conventional workflow Nool must beat for a product-level claim.

For footprint robustness, run a scheduling arm with `--fp-noise-drop P` and
`--fp-noise-add Q` (both probabilities in `[0,1]`) plus a recorded
`--fp-noise-seed`. The former independently removes declared files; the
latter adds one unrelated corpus file to a ticket. `footprint_noise` stores
the original and perturbed footprints per ticket. Results also include
`throughput_accepted_per_min`, computed from end-state accepts and measured
dispatch-to-completion wall time. The conditional rescoring pass is excluded
from that timing.

Corpus v3.1 marks eight behavioral tickets as `tier: "ambiguous"`: their
prompts state observable outcomes while hidden tests define the contract,
without dictating a new function signature or implementation. Select just
that deployment-relevant tier with `--tier ambiguous`; older corpus files are
implicitly `prescriptive`.

For another language or imported benchmark, pass `--task-root tasks/<name>`.
The task's corpus JSON defines argument-array `build`, `test`, and `accept`
commands; the last contains `{ticket}`. The runner records those commands and
the corpus's `repository`, `language`, `source_kind`, and
`footprint_source`, plus the SHA-256 of
the frozen protocol selected by `--protocol`. Validate new corpora with:

```bash
python3 harness/validate_protocol.py tasks/<name>/<tickets-file>.json
```

Shared CI, ownership, and policy documents are committed before arm setup so
every agent worktree sees them. The built-in Go corpus keeps its original
Go-specific policy; other languages receive a command-derived neutral policy.
Files an imported starter already ships are kept as-is (never overwritten),
so the treatment stays deterministic per corpus and identical across arms.

`--harness scripted` runs the deterministic no-LLM adapter
(`adapters/scripted.py`): real minimal solutions for the v1-corpus tickets,
with t3/t7 built to conflict textually so the merge, CI-gate, lease, and
retry paths are all reachable at zero cost. Its records go to
`results/trackc/validation_runs.jsonl`, never `fleet_runs.jsonl` — they
validate harness plumbing and are excluded from evidence by protocol rule
(`exclude_scripted_adapter_from_evidence`). Every arm has at least one
recorded scripted validation run.
