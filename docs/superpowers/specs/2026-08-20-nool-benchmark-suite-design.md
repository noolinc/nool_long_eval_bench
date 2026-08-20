# Nool Benchmark Suite — Design Specification

**Date:** 2026-08-20
**Status:** Draft for review
**Purpose:** Rebuild the nool benchmark collection into an academically defensible,
reproducible experiment suite measuring whether nool materially improves coding-agent
outcomes — sufficient to support enterprise adoption of nool as the coordination layer
("air traffic controller") for coding agents across harnesses (Claude Code first;
Gemini CLI, Codex CLI, Pi later).

---

## 1. Hypotheses under test

Every benchmark exists to support or falsify one of these claims. Each is stated so
that a null result is publishable.

- **H1 (Correctness):** Agents produce more correct code (higher hidden-test pass
  rate) with nool than with git alone, in both single- and multi-agent modes.
- **H2 (Integration):** Parallel agent work integrates with fewer conflicts and less
  lost work under `nool merge` than `git merge`, specifically when changes touch the
  same file in different regions (AST-mergeable), and no worse otherwise.
- **H3 (Coordination):** Nool's lease/overlap mechanism reduces duplicated and wasted
  work among concurrent agents relative to uncoordinated git.
- **H4 (Guardrails):** Nool's propose/solidify validation rejects broken commits that
  git accepts, and containment limits a rogue agent's blast radius on fleet-mates.
- **H5 (Longevity):** Over long-horizon iterative development, repos under nool
  degrade more slowly (erosion/verbosity slope, checkpoint solve rate) than under git.
- **H6 (Cost):** Nool's happy-path overhead (hook latency, propose/solidify vs
  add/commit) is small relative to its measured benefits. This claim can fail
  independently of H1–H5 and must be reported regardless.
- **H7 (Portability):** Effects in H1–H5 replicate across agent harnesses
  (interaction effect harness × VCS reported explicitly).

## 1b. Outcome-claim framework (added 2026-08-20, before Tracks D-F data)

The adoption thesis is outcome-based: "without nool, sufficiently agentic
development becomes measurably unsafe or expensive; with nool those failures
drop materially." Five outcome claims organize all tracks, and every claim
is scored on the FINAL SYSTEM (hidden tests, invariants, main-branch
health), never on whether nool emitted a warning:

| # | Claim | Killer metric | Instruments |
|---|---|---|---|
| C1 | Agents make better changes | final-task correctness | Tracks C, D, A |
| C2 | Fleets stop interfering | conflict/regression/rework rate | D, B5, A1 |
| C3 | Decisions survive across agents/time | constraint-preservation rate | E (longitudinal), D2 |
| C4 | Safe concurrency scales | correctness at N = 5 vs 50 vs 100 | D scale-ups, B2 |
| C5 | Lower cost per accepted change | accepted changes per $ | D, C |

Priority proofs: (P1) fleet correctness under high concurrency, (P2)
longitudinal institutional memory, (P3) deterministic governance.

**Evidence discipline.** Mechanism findings already collected constrain
what the outcome tracks can show and are reported alongside them — as of
this amendment: B5 (nool merge file-level outcomes ≡ git; semantic layer
classifies but does not act) bounds C2; B4 (test-breaking parseable changes
pass propose and deferred validation) bounds P3 absent governance config;
B7 (bisect misidentifies culprit) bounds the debugging claim. If the
product changes, the benchmarks re-run and the bounds move; goalposts do
not.

**Track E — Longitudinal institutional memory (designed; not yet built).**
M sequential tasks (target 100+, budget-gated) against one repo, with
architectural decisions, exceptions, and migrations introduced at scheduled
points and recorded via each arm's native mechanism (nool: ledger/learn/
steering; git: committed ADR markdown). Killer metric: correctness and
constraint-adherence SLOPE over task index — the baseline is expected to
degrade as history outgrows context reconstruction; nool's claim is a flat
curve. Scoring: hidden tests + a constraint-violation checker per decision.

**Track F — Deterministic governance (designed; not yet built).**
Governance configured via nool's own scaffolding (config init-governance:
steer/trust/gating policies). A battery of prohibited-change scenarios
(bypass auth, unapproved dependency, cross ownership boundary, reverse a
recorded decision without justification) where violation is the EASIEST
route to the agent's stated task. Adversarial conditions: fresh sessions,
no conversational context, alternate harness, and the raw-git bypass path
(agent circumvents nool entirely — the enforcement surface must catch it
or the claim fails). Killer metric: blocked violations / attempted
violations, measured on final repo state. Current B4 evidence predicts
gaps; the benchmark exists to quantify them before and after product fixes.

## 2. Suite structure — three tracks

| Track | What | Why | Cost |
|---|---|---|---|
| **A** | Adapted published benchmarks (CooperBench, SlopCodeBench, later SWE-EVO) | External validity, published baselines, comparability | LLM-in-loop, high |
| **B** | Deterministic mechanism micro-benchmarks (no LLM) | Isolate nool mechanisms; free, perfectly reproducible | Near zero |
| **C** | Custom 2×2 harness (Claude Code ± nool × single/multi) | The direct product claim | LLM-in-loop, medium |

**Tier 1 (build first):** Track B (all five) + Track C core.
**Tier 2:** Track A1 (CooperBench subset), A2 (SlopCodeBench full).
**Tier 3:** A3 (SWE-EVO subset), feature ablations, knowledge-carryover experiment.

---

## 3. Track C — Core 2×2 harness

### 3.1 Experimental factors

- **VCS condition:** `git` | `nool` (nool = git repo + `nool init` + agent hooks
  installed, agent instructed to use nool workflow).
- **Agent mode:** `single` | `multi` (K parallel sub-agents; K fixed per task).
- **Harness:** `claude` (implemented) | `gemini` | `codex` | `pi` (adapter contract
  defined now, implementations later).
- **Repetitions:** N ≥ 5 per cell (configurable). Runs are independent: fresh
  workspace, fresh agent session, no shared caches of task content.

### 3.2 Controls (confounds held fixed across arms)

Grounded in published findings:

- **Specification detail** is fixed per task and identical across all arms
  (The Specification Gap, arXiv:2603.24284, shows integration success collapses
  58%→25% as spec detail drops).
- **Task partitioning** for multi-agent mode is authored once per task (in
  `task.yaml`) and identical across git/nool arms (Co-Coder, arXiv:2606.00953,
  shows partitioning strategy dominates multi-agent outcomes). The harness — not
  the agent, not nool — performs the decomposition and spawns sub-agents, so the
  only manipulated variable is the VCS/coordination layer.
- **Model & version** pinned per experiment run and recorded in provenance.
- **Prompts** are frozen files, hashed into provenance; no interactive steering.
- **Timeouts and turn/budget caps** identical across arms.

### 3.3 Task format

```
tasks/<task_id>/
  task.yaml           # id, language, K (multi-agent width), timeouts,
                      # setup/build/test commands, sub-task decomposition,
                      # spec-detail level tag
  spec.md             # the prompt shown to the agent (single-agent form)
  spec_parts/         # per-sub-agent prompts for multi mode (authored, frozen)
  starter/            # initial repo contents
  hidden_tests/       # held-out acceptance tests; copied in ONLY at scoring
                      # time, never visible to any agent
  smoke_tests/        # optional visible tests (part of spec-detail level)
```

Initial catalog: `redux_go` (from bench_*), `reactivity_rust` (from phase2_*),
plus ≥1 task in CooperBench's task schema so tasks flow between Tracks A and C.
The format is CooperBench-compatible where practical (setup script, test runner,
feature descriptions, golden implementation optional).

### 3.4 Multi-agent protocol

1. Harness creates base workspace (git init + optional nool init), commits starter.
2. For each of K sub-tasks: create isolated worktree/branch (`agent_k`), launch
   harness adapter with `spec_parts/k.md`, capture transcript.
3. Integration phase: merge branches into main sequentially in fixed order —
   `git merge` in the git arm; `nool merge` in the nool arm. No human or agent
   conflict resolution in the default protocol; a conflicted merge is recorded and
   skipped (variant protocol: allow a fix-up agent turn, run as a separate
   condition, never mixed).
4. Scoring: copy `hidden_tests/` into the integrated tree, run test command,
   record per-test results.

### 3.5 Harness adapter contract

Each adapter is a Python module implementing:

```python
class Adapter(Protocol):
    name: str
    def preflight(self) -> AdapterInfo        # version, model id, auth ok
    def run(self, workdir: Path, prompt_file: Path,
            limits: Limits) -> RunResult      # blocking, headless
```

`RunResult` must include: exit status, wall time (ms), and — where the harness
exposes them — token counts (input/output/cache), number of turns, tool-call
count, and the raw transcript path. Fields the harness cannot provide are `null`,
never estimated. The `claude` adapter uses
`claude -p --output-format stream-json --dangerously-skip-permissions` inside the
sandboxed workspace, parsing the stream for exact token/turn/tool counts.
`gemini`/`codex`/`pi` adapters ship as documented stubs with the same contract.

**Estimation ban:** no `chars/4` token estimates anywhere in the suite. Metrics a
harness does not expose are reported as missing.

### 3.6 Metrics (Track C)

Per run: hidden-test pass fraction; build success; merge outcomes (clean /
conflicted / aborted per branch); tokens in/out; turns; tool calls; wall time ms;
harness/model/nool/git versions; prompt hashes; full transcript archived.

### 3.7 Statistics & reporting

- Success rates with 95% Wilson intervals; token/time as median + IQR
  (agentic runs are heavy-tailed; means reported secondarily).
- Cell comparisons: two-sided Fisher exact (success) and Mann-Whitney U
  (tokens/time). With small N, report effect sizes and intervals; no p-value
  theater at N=5 — the analysis script labels underpowered comparisons as such.
- **Analysis code emits numbers and plots only. No prose conclusions in code.**
  (Replaces the hardcoded-conclusion pattern in the archived `run_ag_evals.sh`.)
- Raw per-run JSONL is retained and committed (or archived) alongside summaries;
  every figure regenerable from raw data by `analysis/summarize.py`.

---

## 4. Track B — Mechanism micro-benchmarks (deterministic)

All scripted, no LLM, timing via monotonic clocks at millisecond resolution,
M ≥ 20 repetitions per measurement, medians reported. Each emits JSON and a
pass/fail assertion where the claim is binary.

- **B1 Overhead tax:** (a) per-hook latency of `claude_hook.sh` on
  PreToolUse/PostToolUse/Stop events, measured by direct invocation with recorded
  event payloads; (b) `nool propose --fast` + `solidify` vs `git add`+`commit` on
  matched change sets (1, 10, 100 files); (c) end-to-end tax: scripted N-operation
  editing session replayed with hooks on vs off.
- **B2 Live concurrency:** N scripted writers (N ∈ {2, 5, 15, 50}) performing
  interleaved edit/propose cycles concurrently in one workspace family. Metrics:
  throughput (ops/s), lock-wait time, lost-update count (assert 0), final-state
  integrity check. Git arm uses branch-per-writer as its concurrency story.
- **B3 Recovery:** inject a known-bad change amid ongoing good work; measure
  command count and wall time to restore known-good state (`git revert/reset` vs
  `nool rewind`), and assert whether unrelated concurrent work survives intact
  (collateral-damage check, diff-verified).
- **B4 Guardrails (rogue commit):** matched arms — syntactically broken, and
  test-breaking-but-parseable changes committed via git (control: git accepts) vs
  proposed via nool (measure: rejected at propose? at solidify? accepted?).
  Explicit assertions; exit code non-zero when the guardrail claim fails.
- **B5 Swarm merge (hardened from `run_swarm_benchmark.sh`):** scenarios
  (a) disjoint files — negative control, both must succeed;
  (b) same file, same anchor line — worst case, both expected to conflict;
  (c) **same file, different functions/regions** — the AST-merge case where nool
  can differ from git; this scenario is the crux of H2 and is missing today.
  Fixes over the current script: monotonic ms timing; nool-arm conflict handling
  uses nool's own abort path (never `git merge --abort` inside the nool arm);
  DAG-head count read via a machine-readable nool command if available, else the
  parse is marked fragile in output; results JSON includes provenance block.

- **B6 Context retrieval (added 2026-08-20):** nool's differentiator claims
  include semantic history queries and AST-level context ("structured flow"
  for models). Build a repo knot-by-knot with recorded intents and a known
  ground-truth feature; compare bytes an agent must ingest and hit-rate for
  `nool query search` / `query context <file>#<symbol>` (and the chained
  search-then-context flow) against the grep-then-read-full-files baseline.
  Bytes reported as bytes; no token conversion.
- **B7 Regression localization (added 2026-08-20):** seed K landings with a
  known culprit; `nool debug bisect --good --bad --test` vs
  `git bisect run` with the identical test. Metrics: correct culprit named,
  wall time, steps. (`--bad` must be explicit in nool 6.13; the HEAD default
  resolves outside knot-id space.)

**Prerequisite finding to investigate during implementation:** the existing
`swarm_bench_results.json` shows nool ≡ git on the contended scenario (1 clean /
14 conflicts). Before building B5(c), verify with nool's documentation/CLI what
merge semantics `nool merge` actually applies, so the benchmark tests the
mechanism nool claims, not our assumption of it. If nool does not perform
semantic merge in this path, H2 is tested against whatever path does (and the
docs' claim is cited in the task README).

---

## 5. Track A — Adapted published benchmarks

- **A1 CooperBench (Tier 2):** ~30–50 task subset stratified across its 12 repos
  and 4 languages. Arms: their coop mode as published (git + Redis messaging)
  vs coop mode with nool as the coordination substrate (leases + nool merge).
  Metrics: their per-feature pass, plus our conflict/duplication counts; failures
  classified with their taxonomy (expectation/communication/commitment).
  Integration work: wire nool into their workspace setup (Docker backend first).
- **A2 SlopCodeBench (Tier 2):** full 20 problems × checkpoints, with/without
  nool. Metrics: checkpoint solve rate, erosion slope, verbosity slope across
  checkpoints. The comparison of **degradation slopes** between arms is the H5
  long-horizon result; published baselines give context.
- **A3 SWE-EVO subset (Tier 3):** realistic multi-file evolution tasks; pass rate
  + their Fix Rate partial-credit metric.

Each adaptation lives in `external/<bench>/` with a pinned upstream version,
a patch/overlay directory (never a fork-in-place), and a README stating exactly
what was changed and why.

---

## 6. Repository restructure

```
nool_benchmarks/
  README.md                  # methodology, hypotheses, how to reproduce, tier status
  docs/superpowers/specs/    # this spec
  archive/                   # ALL current dirs & scripts moved here verbatim
    ARCHIVE.md               # inventory + why each item is pilot data, not evidence
  tasks/                     # Track C task catalog (format §3.3)
  harness/
    run_experiment.py        # cells × reps orchestration, resumable
    adapters/{claude.py, gemini.py, codex.py, pi.py}
    scoring.py, provenance.py
  micro/                     # Track B: b1_overhead ... b5_swarm_merge
  external/                  # Track A adaptations (Tier 2+)
  results/                   # raw JSONL per run (gitignored large transcripts,
                             # index committed)
  analysis/
    summarize.py             # stats + figures; numbers only
requirements: Python 3.11+, stdlib-only where possible (no heavy deps).
```

Archived items and their disposition: `run_ag_evals.sh` (hardcoded conclusion —
archived, cited as anti-pattern), `parse_metrics.py` (machine-specific,
estimation-based), `run_empirical_merge_test.sh` (demo, no nool arm),
`run_rogue_test.sh` (superseded by B4), `run_swarm_benchmark.sh` (superseded by
B5), `bench_*`/`phase*` dirs (manual pilot outputs; starter code recycled into
`tasks/`).

## 7. Threats to validity (reported in README, mitigations built-in)

- **Prompt sensitivity to nool:** the nool arm's agent must know nool exists
  (skill/hook injection), which changes the prompt context vs the git arm.
  Mitigation: identical task spec; nool context arrives only via nool's standard
  hook mechanism, exactly as a real user would experience; context sizes logged.
- **Author bias:** benchmarks written by nool's author. Mitigation: hypotheses
  pre-registered in this spec before Tier 1 runs; negative controls (B5a) where
  no difference is expected; all raw data published; analysis code conclusion-free.
- **Small N / cost ceiling:** underpowered cells labeled; deterministic Track B
  carries mechanism claims at high N.
- **Harness drift:** model/CLI versions pinned & recorded; reruns report their own
  provenance rather than claiming comparability across versions.
- **External benchmark integration bias:** overlays are minimal diffs, published.

## 8. Replication package (external-validation requirements)

A third party with no contact with us must be able to validate results. Concretely:

- **One-command runs:** `make tier1` (Track B + C smoke), `make trackB` (free, no
  API keys), `make trackC HARNESS=claude N=5`. Track B must run anywhere with
  Docker alone — it is the zero-cost validation entry point.
- **Containerized execution:** all Track B/C runs execute in pinned Docker images
  (base image digest recorded in provenance). Agent CLIs run with permissive
  flags only inside the container.
- **Pinned everything:** model IDs, agent CLI versions, nool version, git version,
  image digests — recorded per run and asserted at startup (run refuses to start
  if versions drift from the manifest unless `--allow-drift` is passed, which is
  stamped into the results).
- **Nool access for validators:** external validation requires running nool.
  A no-cost evaluation license (or free tier) covering the benchmark duration
  must be available to replicators, and the exact nool build archived. **This is
  an adoption-team dependency, flagged now: without it, external validation of
  every nool arm is impossible.**
- **Cost disclosure:** README publishes measured cost (USD + tokens) per cell so
  replicators can budget before running.
- **Replication ≠ identical numbers:** the package promises protocol
  reproducibility; LLM nondeterminism means replicators generate their own
  provenance and compare effect directions/magnitudes, not exact values. Stated
  in README to preempt reviewer confusion.

## 8a. Track D — Fleet Operations Benchmark (pre-registered 2026-08-20, before any Track D data)

The enterprise scenario the suite must speak to: N real agents processing a
ticket backlog against ONE shared existing codebase, with the coordination
layer as the manipulated variable. This operationalizes H3 (coordination) and
the "air traffic controller" adoption claim.

**Setup.** A self-contained synthetic Go service (~12 files, 4 packages,
stdlib-only; synthetic-but-realistic, disclosed as such) with a passing smoke
suite. A backlog of 8 tickets, each specifying required API signatures and
its expected file footprint. Overlap is designed in: three contention
clusters share hot files ({T1,T6,T8} on service/users.go; {T2,T5} on
service/orders.go; {T3,T7} on api/*), one ticket is disjoint. One acceptance
test per ticket, hidden until scoring; each must FAIL on the base tree
(verified at task QA) and pass iff the ticket is correctly implemented.

**Arms.** Identical agent prompts (ticket text + "land your work with the
repository's workflow"); identical model; N=5 worker slots; agents work in
isolated worktrees and commit to ticket branches in both arms.
- `git_fleet` (uncoordinated baseline): all tickets dispatched in parallel;
  integration = sequential `git merge` queue in ticket order; conflicts
  recorded, not resolved.
- `nool_fleet` (coordinated): tickets registered as nool tasks; before
  dispatch the orchestrator runs `announce intent --target-nodes <footprint>`
  and `discover conflicts <footprint>` per ticket; tickets whose footprints
  conflict with in-flight work are HELD until the conflicting ticket
  integrates (gated dispatch — nool's documented coordination pattern);
  integration = `nool merge`; tasks closed on integration.
The asymmetry (gated vs ungated dispatch) IS the treatment: each arm uses
its layer's native coordination capability, and git has none. Disclosed.

**Metrics.** Wall time to backlog completion; per-ticket acceptance pass;
integration conflicts; main build+test health after every merge; wasted
agent spend (cost of tickets that fail integration); attribution
completeness of resulting history; total cost. Failure taxonomy per
unsuccessful ticket: agent-failure / integration-conflict /
interface-mismatch (clean merge, broken build).

**Reps.** Pilot = 1 rep per arm (pipeline validation + effect direction);
labeled underpowered. Scaling to ≥3 reps is a budget decision recorded
before scaling.

**Scenario D2 — Handoff/rehydration (pre-registered with D, before data).**
Fleet agents are routinely interrupted (context limits, crashes, budget
caps); the controller claim includes cheap handoff: a successor agent
rehydrates from recorded state and continues. Protocol: agent A runs the
`redux_go` full spec with a hard cap of 4 turns (observed solo completion
needs ~6-7), landing whatever exists at cap; a FRESH agent B receives the
identical prompt in both arms: "A previous engineer was interrupted partway
through this task. Recover their progress from this repository's history and
workflow, then complete the task." Arms differ only in what the workspace
provides for recovery: git log/diff vs nool status/log/intents (hooks
installed). Metrics: B's hidden-test pass, B's turns/tokens (context
re-acquisition cost), redundant work (functions A landed that B rewrote,
measured by diff), N=3 pairs per arm minimum.

## 8b. Track C follow-up condition: structured task flow (Tier 2, designed)

Nool's task system (`task create/pick/start/qa/finish`, acceptance criteria,
`fleet plan` disjoint waves) is a claimed coordination differentiator the
current multi-agent protocol does not exercise (worktree sub-agents are
outside nool tracking by design). A fifth condition, `multi_nool_tasked`,
will run sub-agents sequentially in the shared nool workspace with the
decomposition pre-registered as nool tasks. Prompt parity is preserved
structurally: both arms' prompts say "consult this repository's task system
for your assignment"; in the git arm that is a committed TASKS.md, in the
nool arm the task board. Measured: coordination outcomes (duplicate work,
interface mismatches at integration), token cost of task-context retrieval,
and lease/announce conflicts if agents overlap.

## 9. Out of scope (this iteration)

Nool fleet/orchestration as the multi-agent driver (tests a different claim —
noted as future condition), knowledge-ledger carryover (Tier 3), human-developer
baselines, cross-repo enterprise simulations.
