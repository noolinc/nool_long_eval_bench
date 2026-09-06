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

<a id="sec-5"></a>
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

<a id="sec-8"></a>
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

<a id="sec-8a"></a>
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

**Scale-up 1 (pre-registered 2026-08-20 after pilot, before scale data).**
Pilot runs 1–2 showed file-footprint overlap absorbed by textual merge: the
uncoordinated baseline did not fail, so no arm difference was measurable.
Scale-up 1 raises contention to the function level and widens the fleet:
- Corpus v2: the 8 pilot tickets plus 12 new (20 total) with three designed
  clusters — A: three tickets each modifying the SAME function body
  (service/billing.go Invoice — the regime where B5 shows textual merge
  fails); B: three tickets modifying the same handler file's functions;
  C: three tickets extending the same store file; plus 3 independent
  fillers. Cluster-A acceptance tests assert each ticket's property with
  tolerance for the other cluster members' presence, so a ticket's score
  reflects ITS feature landing, not its neighbors'.
- N = 10 workers, 2 reps per arm, same pinned model.
- Predicted (falsifiable): git arm suffers integration conflicts on
  cluster A's 2nd/3rd merges (branches share a base; same-function edits);
  nool arm's gated dispatch serializes the cluster so later tickets branch
  from integrated state and compose. If the git arm again absorbs the
  contention, that is reported as-is and the next escalation is
  spec-level interaction (tickets whose CHANGES semantically interact).
- Metrics as in D, plus per-cluster integration outcomes and wasted spend
  (cost of agent runs whose tickets failed integration).
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

**Scale-up 1 confirmation on corpus v2.1 (pre-registered 2026-08-21,
before any v2.1 data).** Scale-up 1's nool reps' sole failure (t2, both
reps) was traced to a corpus artifact, not agent quality: v2's t2
acceptance test hard-coded pre-cluster-A invoice totals (880 cents) and
failed whenever ALL of cluster A landed — penalizing exactly the arm that
successfully integrates every contended ticket. Corpus v2.1 rewrites t2's
acceptance test as property checks routed through the service's own
functions (verified green against both plain-starter and
full-cluster-A Invoice semantics before landing); ticket specs unchanged.
Confirmation design, identical to scale-up 1 in every other respect:
N=10 workers, corpus v2.1 (20 tickets), 2 reps per arm, claude-sonnet-5
pinned, nool 6.14.1, sequential runs under the RAM watchdog.
Predictions (falsifiable):
- nool arm accepts 20/20 in each rep; any failure that does occur is
  reported as-is with its taxonomy label (a recurrence of a t2 failure on
  the property test would indicate agent quality, not the artifact).
- git arm remains bimodal with integration conflicts on cluster 2nd/3rd
  merges and acceptance at or below its prior 13/20; the t2 fix should
  not materially change git outcomes, because the artifact fired only
  when all of cluster A landed, which no git rep achieved.
Metrics and scoring identical to scale-up 1. Reporting: these reps become
the primary corpus-v2.1 comparison; run-3 (v2) reps are retained in the
manifest, annotated with the artifact.

**Confirmation outcome (recorded 2026-08-21, after the quartet).** git
12/20 and 13/20 (prediction met: bimodal good mode, cluster 2nd/3rd-merge
conflicts, health green). nool 19/20 and 18/20 — the 20/20 prediction was
FALSIFIED, and the cause was a new corpus artifact, not the arms: v2.1's
t2 property test pinned one of two valid floor readings of the spec text
and t2 failed in all four runs in both arms. Corpus v2.2 corrects the
rounding check to admit both readings (validated against both readings
crossed with plain and full-cluster-A Invoice semantics). No further
N=10 reruns on the 20-ticket corpus: the scale-up 2 ladder's low-N anchor
on corpus v3 (below) carries the corrected test forward.

**Scale-up 2 — concurrency ladder (pre-registered 2026-08-21, before any
corpus v3 or N>10 data).** Corpus v3: 60 tickets = the 20 v2.2 tickets
plus 40 new (t21-t60): 20 contended tickets deepening eight hot surfaces
(billing Invoice body grows to a 5-ticket same-function cluster; users
Create body 5 including t6; api reaches 10 tickets across handlers/router
with four Router-wide behaviors; store 6; orders 6; util/ids 4;
model/user 4) and 20 independent single-file fillers. All new acceptance
tests are property-based and neighbor-tolerant; a committed harness
(tasks/fleet_service/validation_v3/) proves every acceptance test green
against combined reference implementations per cluster AND with all 60
tickets implemented simultaneously, smoke included — the check both t2
artifacts would have failed. One carryover test (t3) was hardened for
neighbor tolerance (distinct emails); no ticket specs changed.
- Ladder: N in {10, 25, 35, 50} workers, corpus v3 throughout, 2 reps per
  arm per point, claude-sonnet-5 pinned, nool 6.14.1, runs strictly
  sequential under the RAM watchdog (abort at <8% free memory on two
  consecutive samples). N=10 anchors the ladder (corpus differs from
  scale-up 1, so the anchor is re-measured). Points run lowest-N first.
- Guarded attempts: a higher point runs only if the previous point
  completed without a watchdog abort. An aborted run is recorded and
  reported as an infrastructure limit of the 16 GB operator machine —
  never as an arm outcome — and remaining runs at and above that N are
  skipped. At the observed 0.4-0.65 GB RSS per headless worker, N=25 is
  expected marginal and N=50 is expected to exceed local RAM; the guarded
  ladder measures where the ceiling actually is. Estimated spend at the
  observed ~$0.19/ticket: ~$11-12 per run, ~$90-190 for the ladder
  depending on how far it climbs.
- Predictions (falsifiable): (1) nool acceptance stays within +/-2 tickets
  of its own anchor rate at every completed point, with zero
  integration-conflict failures (any failures are agent-quality); (2) git
  acceptance declines with N — at N>=25, git accepts <=45/60 per rep, and
  at least one git rep across the ladder shows a clean-merge
  build-poisoning event like scale-up 1's t17; (3) nool wall time grows
  with N faster than git's (serialized hot clusters) but nool cost per
  accepted ticket stays at or below git's at every completed point.
- Metrics: as scale-up 1, plus per-N acceptance curves per arm and, per
  run, the watchdog log's minimum free-memory reading as the concurrency
  cost record.
- Decision rule (C4): supported if, at the highest completed N, nool's
  acceptance is within +/-2 tickets of its anchor while git's has declined
  by >=5 tickets from git's anchor; unsupported if nool declines
  comparably to git; points censored by the watchdog are reported as
  infrastructure-censored, not evidence in either direction.

<a id="sec-8b"></a>
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

<a id="sec-8c"></a>
## 8c. Track D — arm-decomposition study (pre-registered 2026-08-22, before any arm-B/C/D data)

**Implementation audit (2026-08-22), disclosed as a deviation from §8a's
description.** A code audit of `harness/fleet_run.py` against §8a found the
`nool_fleet` arm's dispatch gating was computed by the harness, not by nool:
admission is a Python set-intersection over each ticket's corpus-declared
footprint; `nool announce intent` and `nool discover conflicts` run only
AFTER admission is decided and their output is recorded but never consulted.
All recorded `discover` verdicts across every collected run are the identical
no-conflict boilerplate. Tickets were never registered as nool tasks, despite
§8a saying so. A CLI probe further established that nool's actual
coordination primitive is the announcement itself: an `announce intent`
whose target nodes overlap an active lease is REFUSED with exit code 3 and
"Coordination conflict", while `discover conflicts` reports no conflicts
even against an active overlapping lease. Consequences, pre-registered
before any new data: (1) all collected fleet results are re-described as
measuring the footprint-gated dispatch POLICY under oracle (corpus-declared)
footprints, with product attribution an open question; (2) the arms below
decompose the effect. Collected data is retained unchanged; the `nool_fleet`
arm's harness code is frozen as-is for continuity.

**A second structural observation, also disclosed:** in the `git_fleet` arm
every agent branches from the same base commit and all merges run after all
agents finish, so the merge queue's inputs are statistically independent of
N. Observed corpus-v3 conflict counts confirm this: 21-22 at N=20, 20-21 at
N=25, 21-22 at N=35. C4's "git declines with N" reading is therefore not
supported by the ladder's design; what varies with N in the collected data
is stochastic build-poisoning severity at 2 reps per point. C4 evidence
wording is downgraded to "separation holds at every measured N" until a
design in which N mechanically varies contention exposure exists.

**Negative corpus validation (added, run 2026-08-22, deterministic).**
`tasks/fleet_service/validation_v3/validate_negative.py` proves every
acceptance test FAILS on the plain starter (60/60) and FAILS when every
other cluster's reference implementation is applied while its own stays at
starter (all clusters green; complement workspaces verified to build).
Within-cluster leave-one-out — the t21 class, where a cluster-mate's change
satisfies a conflicted ticket's test — is NOT covered (requires per-ticket
decomposed references; deferred to corpus v3.1) and is instead detected
empirically: `analysis/summarize.py` now flags accepted-without-landing
tickets per run (currently exactly t21, both git N=20 reps and both N=25
reps).

**New arms** (harness `fleet_run.py`; prompts, model, worker slots,
worktree isolation, launch stagger, and scoring identical to §8a arms):
- `git_gated_queue`: parallel dispatch as `git_fleet`; the sequential merge
  queue becomes CI-gated — after each textually-clean merge the harness
  runs build+smoke and, on red, resets main to the pre-merge commit and
  records the ticket as queue-rejected. Models the industry-standard
  test-gated merge queue; isolates how much of `git_fleet`'s loss is the
  blind queue rather than git.
- `git_scheduled`: footprint-gated dispatch using the IDENTICAL harness
  scheduler as `nool_fleet` (oracle footprints, same admission logic, same
  same-batch gating), integration by plain `git merge`, no nool anywhere.
  The attribution ablation: any `nool_fleet` advantage over this arm is
  product; any `git_scheduled` advantage over `git_fleet` is policy.
- `nool_gated`: dispatch gated by nool itself — at each scheduling tick a
  pending ticket is admitted iff `nool announce intent --target-nodes
  <footprint> --agent-id agent_<tid>` succeeds (exit 0); refusals (exit 3)
  hold the ticket, re-attempted after a lease release. The lease is
  released (`nool announce release`) after integration; integration is
  `nool merge`. Every announce attempt and release is recorded. Footprints
  remain corpus-declared in this arm (footprint-source robustness is a
  separate, later condition).
- Starter-tree integrity is now machine-enforced: every run hashes
  `tasks/fleet_service/starter` and refuses to start on mismatch with the
  pinned `tasks/fleet_service/STARTER_SHA256` (audit trail from the
  corpus-contamination incident).

**Protocol.** Corpus v3, claude-sonnet-5 pinned, N=35 (the highest
completed ladder point), sequential runs with the launch stagger; 5 reps
per new arm, plus 3 additional `nool_fleet` reps to reach 5 at N=35.
Estimated spend at observed ~$7/run: ~$125-130 total.

**Predictions (falsifiable, recorded before any data):**
1. `git_gated_queue` accepts 60 minus its conflict count (expected 38-41
   per rep) with ZERO cascade failures and final health green in every
   rep — i.e., the CI gate fully eliminates the build-poisoning mode.
2. `git_scheduled` accepts >=58/60 per rep with zero integration
   conflicts — statistically indistinguishable from `nool_fleet`.
3. `nool_gated` matches `nool_fleet` within +/-2 tickets with zero
   conflicts; its gating log shows real refusals (exit 3) for cluster
   tickets, and its wall time exceeds `nool_fleet`'s by the announce
   overhead (recorded per attempt).
4. Conditional acceptance (accepted given landed) stays at ~100% in every
   arm — the arms differ in what lands, not in agent code quality.

**Decision rule (attribution).** The §8a/§5.5 separation is attributed to
the coordination POLICY if prediction 2 holds. nool's product contribution
is then the delta between `nool_gated` and `git_scheduled` (native leasing
vs harness logic: correctness of refusals, overhead, and operational
convenience), NOT the headline acceptance delta vs `git_fleet`. If
prediction 2 fails (git_scheduled materially below nool_fleet), the product
retains outcome-level credit and the failure mode is documented. If
prediction 1 fails, the poisoning mode is deeper than queue policy and the
`git_fleet` baseline stands closer to fair. Claims C2/C4/C5 are re-worded
against whichever branch obtains; goalposts above are fixed now.

**Replication access (updates §8's license dependency).** Nool's free tier
— 2,000 knots per project for 30 days — covers full replication: measured
consumption is 62 knots per 60-ticket fleet run and ~90 for the largest
Track B cell; a complete suite replication is ~1,200-1,500 knots. To
confirm before the README cites it as the official path: whether throwaway
benchmark workspaces each count as a project, free-tier feature parity
(--fast, ghost-run validation, announce/discover/release, MergeReconcile,
pluck, bisect, query, hooks), and absence of tier-specific latency or
throttling (B1/B2 measure latency). Remaining replicator cost is LLM spend
(~$7-10 per fleet run), already disclosed.

<a id="sec-8d"></a>
## 8d. Track D — footprint-source robustness (pre-registered 2026-08-27, before any 8d data)

§8c's `nool_gated`/`git_scheduled` arms both gate on a corpus-declared
(oracle) footprint; §8c explicitly deferred the question of what happens
when that footprint is wrong (line ~578: "footprint-source robustness is
a separate, later condition"). Two prior observations motivate testing it
now rather than later: (1) real-agent footprint drift already happened
once, uncontrolled — findings §6b's `t30` (`nool_gated`, N=25): an agent
edited a file outside its declared footprint, triggering a genuine
propose-stage refusal; (2) the harness already implements a controlled
noise mechanism (`fleet_run.py --fp-noise-drop P --fp-noise-add Q
--fp-noise-seed S`, `harness/README.md`) that has never been exercised
for evidence — zero `fleet_runs.jsonl` records carry `footprint_noise`
data as of this writing.

**Mechanism (already implemented, no new harness code required).** Before
dispatch, each ticket's declared footprint independently drops each file
with probability `fp_drop`, then with probability `fp_add` appends one
spurious file drawn from the corpus-wide footprint universe. Perturbation
is recorded per-ticket (`footprint_noise` field) for exact
reproducibility. Both arms under test receive the *identical* perturbed
footprint for admission gating — the noise models an imperfect footprint
source, not an information asymmetry between arms. What differs is what
each arm does after a bad admission decision: `git_scheduled` integrates
with a blind `git merge` (no recovery once past scheduling); `nool_gated`
integrates with `nool merge`, which may still surface a real overlap at
merge time via nool's own conflict machinery even after the (equally
noisy) admission gate let it through.

**Scope.** `nool_gated` vs `git_scheduled`, corpus = whatever
`tasks/fleet_service/tickets_v3.json` currently declares (`v3.1` as of
2026-08-27 — see findings §6c), N=20 (revised up from an initial N=10
choice: N is worker concurrency, not ticket count, so cost is flat across
N while higher concurrency gives noise-induced bad admissions more
in-flight tickets to actually collide with). Two noise cells, **1 rep per
arm per cell** (reduced from an initial 3-rep design under an operator
weekly-quota constraint — every cell below is consequently a single-rep,
UNDERPOWERED first look by this suite's own convention, not a
confirmatory measurement; scaling to 3+ reps is the natural next step if
the direction looks interesting):

| Cell | fp_drop | fp_add | Models |
|---|---|---|---|
| light | 0.1 | 0.1 | minor footprint miss/over-declaration |
| heavy | 0.3 | 0.3 | materially unreliable footprint source |

**Zero-noise anchor, included in this pre-registration (not previously
collected):** no existing `claude-sonnet-5` zero-noise data exists for
`nool_gated`/`git_scheduled` at N=20 specifically — the closest prior
point is N=10/v3 (`nool_gated` 60/60 both reps, `git_scheduled` 60/60
both reps; README "Current status", findings §6a/6b), which does not
transfer since N itself differs, not just noise. **1 rep per arm** at
`fp_drop=0, fp_add=0`, N=20, same corpus, is added to this
pre-registration as the matched baseline predictions 1-2 are judged
against (also reduced from an initial 2-rep design, same quota
constraint). This anchor is also the first `claude-sonnet-5` N=20 data
point for these two arms on any corpus (the existing off-ladder N=20
point, README "Current status", covers `git_fleet`/`nool_fleet` only,
plus a weak single-rep opencode trial for this pair).

**6 runs total**: 2 zero-noise (2 arms x 1 rep) + 4 noise (2 arms x 2
noise cells x 1 rep). Estimated spend at observed ~$7-9/run (cost is
driven by the fixed 60-ticket corpus, not by worker count N): ~$45-55.

**8d-i, rep 2 (pre-registered 2026-08-27, before rep-2 data; results
below are rep 1 only).** Rep 1 (§6d) found prediction 1 non-monotonic for
`nool_gated` and prediction 2 holding only directionally at heavy noise —
both readings explicitly flagged as unsettled at n=1. A second rep per
cell is added: same arms, N, corpus, and noise levels; new independent
`fp-noise-seed` values for the noise cells (rep 1 used 1001/light,
1002/heavy — rep 2 must use different seeds, shared between the two arms
within a cell as before, so the perturbation is identical across arms but
independent of rep 1's draw). 6 more runs (2 arms x 3 cells x 1 rep),
~$45-55 more, bringing every cell to 2 reps. Two reps still does not meet
the "3+" bar the spec's own convention treats as minimally powered, and
this must be disclosed alongside any updated reading — but it does let
predictions 1-2 be checked against a second, independent draw instead of
resting on one.

**8d-i, very-heavy cell (pre-registered 2026-08-27, before this cell's
data).** Rep 1+2 (§6d-§6f) found the degradation curve holding cleanly
through `fp_drop=0.3, fp_add=0.3` (heavy): `nool_gated` 58/60 both reps,
`git_scheduled` 55/60 both reps. A third noise level, `fp_drop=0.5,
fp_add=0.5` ("very heavy" — half of every ticket's declared footprint is
wrong), extends the curve one step further: 2 reps per arm, N=20, same
corpus, new independent seeds (3001 for rep 1, 3002 for rep 2, shared
between the two arms within each rep as in every prior cell). 4 runs
(2 arms x 2 reps), ~$32-36 more. **Prediction (falsifiable, before this
cell's data):** the degradation curve continues in the same direction —
`git_scheduled`'s accept rate falls further below `nool_gated`'s than at
heavy noise (i.e., the gap widens, not narrows or reverses). If the gap
narrows or `git_scheduled` overtakes `nool_gated` at this noise level,
the "advantage widens with noise" reading from §6f is falsified and the
heavy-noise result should be treated as a local, not general, pattern.
Still n=2/cell — this remains a provisional read, same caveats as every
other §8d-i cell.

**Predictions (falsifiable, recorded before any data; read as directional
given n=1/cell, not statistically confirmatory):**
1. Both arms' accept rate declines monotonically from the zero-noise
   anchor as noise increases (light > heavy in degradation) — the
   mechanism should visibly bite, not be absorbed silently.
2. `git_scheduled`'s accept-rate decline at heavy noise is larger than
   `nool_gated`'s. Rationale: `nool_gated`'s `nool merge` step is a
   second opportunity to catch a true overlap that a corrupted admission
   gate let through; `git_scheduled`'s blind `git merge` has no such
   backstop once scheduling is fooled.
3. Conditional acceptance (accepted given landed, per `harness/README.md`
   §"Fleet protocol") stays near 100% in both arms at every noise level —
   any effect is on what integrates, not on code quality once integrated.
4. `nool_gated`'s gating log shows a measurable rate of exit-3 refusals
   correlated with `fp_add`-injected spurious files (nool refusing a
   ticket over a footprint entry that was never real) — a distinct,
   nool-specific failure mode (false-positive contention) not observable
   in `git_scheduled`, which has no equivalent live refusal signal.

**Decision rule.** If prediction 2 holds, footprint-source robustness is
a genuine, measured product advantage for `nool_gated` over the
identically-gated `git_scheduled` baseline — the first evidence in this
suite that nool's contribution is not fully explained by the
policy-not-tool reading of §6a/§8c. If prediction 2 fails (equal or
worse degradation for `nool_gated`), the policy-not-tool reading extends
to this axis too: both arms are equally exposed to a corrupted footprint
source, and nool's real merge-time machinery provides no additional
robustness over blind git merge. Either outcome is reported; goalposts
above are fixed now, before any 8d data exists. At n=1/cell this decision
rule is provisional — a single rep flipping the other way on rerun would
overturn it — and any 8d-i result must be labeled UNDERPOWERED and framed
as motivating replication, not as settling the question.

**Follow-up, explicitly out of scope for 8d-i:** 8d-ii — replacing the
oracle-plus-noise footprint with a real inference step (static analysis,
an LLM-predicted footprint, or nool's own semantic footprint machinery,
if any) rather than perturbing a known-correct declaration. This requires
new harness code and is not pre-registered here.

<a id="sec-8e"></a>
## 8e. The mechanism question, and a redirected roadmap (proposed 2026-08-27, not yet pre-registered)

§8d established a correlation (nool_gated degrades more slowly than
git_scheduled as footprint noise rises) without establishing why. Six
candidate mechanisms are equally consistent with the data collected so
far, and no experiment run to date discriminates among them:

1. **Dynamic lease behavior** — nool_gated's live `announce`/release
   retry loop behaves differently under load than the harness's static
   footprint-intersection scheduler, independent of noise per se.
2. **An asymmetry in how the two arms are exposed to the same
   corruption** — both receive identically-perturbed footprints, but
   `nool merge`'s extra step and `git merge`'s absence of one could
   interact with that corruption differently (the leading hypothesis
   from §6d, never directly observed).
3. **Ticket topology** — the specific corpus clusters (e.g. the
   `service/billing.go` family, §6f) may be more or less exposed to
   noise depending on which arm happens to serialize them in which
   order; §6f already flagged this as an open, unresolved alternative
   to a real per-arm difference.
4. **Retry behavior** — how each arm's dispatch loop responds to a
   refused or failed ticket (immediate retry vs. backoff vs. queue
   position) could matter independent of the footprint information
   itself.
5. **Nool's semantics** — some property of nool's merge/conflict
   detection genuinely does catch more true overlaps than blind `git
   merge`, which is the reading this study has favored but never
   isolated from the above four.
6. **Some other implementation detail** not yet identified — the honest
   default given no experiment has discriminated among 1–5.

**Recommendation: stop optimizing the concurrency ladder (N=50) and
redirect toward this question instead.** N=50 tests whether the
policy-level separation established through N=35 continues to hold at
higher concurrency — a question this suite has already answered
directionally at every rung tested (§6, findings). It does not touch the
mechanism question above, and carries a known, real memory-exhaustion
risk on the 16GB development machine used for this study (§8a). The
more valuable next step is determining *why* nool_gated's advantage
appears, which §8d-ii below is designed to approach, and *whether it
holds when footprints are agent-discovered rather than
oracle-declared-plus-noise* — the actual real-world condition, since a
production fleet has no oracle to perturb in the first place. N=50
remains pre-registered and open; it is deprioritized, not withdrawn.

### 8e-i. Scaling §8d to its own "3+" bar (buildable now, no new code)

The cheapest, most direct next step: §8d's existing light/heavy/
very-heavy cells are at n=2/cell. Three more reps per cell per arm (18
runs: 2 arms x 3 noise levels x 3 reps) would bring every cell to n=5,
clearing this suite's own convention for a minimally powered read and
directly answering the request to make the existing result "difficult
to dismiss" before adding new uncertainty types. Estimated cost at
observed ~$8–9/run: ~$150.

**Pre-registered 2026-08-27, before this data**: reps 3–5, new
independent `fp-noise-seed` values shared between the two arms within
each rep (light: 5001/5002/5003; heavy: 6001/6002/6003; very-heavy:
7001/7002/7003), same N=20/v3.1/`nool_gated`-vs-`git_scheduled` setup as
reps 1–2. Prediction: the mean gap at each noise level (currently 3.3pp
light, 5.0pp heavy, 6.7pp very-heavy at n=2) stays positive and
ordered — `nool_gated` mean acceptance at or above `git_scheduled`'s at
every level, gap non-decreasing across light→heavy→very-heavy — once
averaged over 5 reps instead of 2. A reversal at any level, or the gap
collapsing toward zero, would weaken §6f/§6g's reading materially more
than a single-rep fluctuation would.

**Execution update (2026-08-27).** The light-noise cell is now complete
at n=5 per arm. The three preregistered additions produced, by shared
seed, `nool_gated`/`git_scheduled` acceptance counts of 57/59 (5001),
58/56 (5002), and 59/57 (5003). Together with reps 1--2, that is
290/300 (96.7%) for `nool_gated` and 284/300 (94.7%) for
`git_scheduled`: a 2.0pp advantage, positive but smaller than the
original n=2 light estimate (3.3pp). The heavy cell's first added
`nool_gated` run (seed 6001) is 55/60; its paired git run and the rest
of the pre-registered heavy/very-heavy runs are not yet included in a
cross-arm estimate. The initial §8d figures remain the balanced n=2
analysis until each cell reaches its planned n=5.

### 8e-ii. An intent-quality degradation battery (proposed; buildability varies by condition)

Six distinct uncertainty types, gated on what each needs to build:

| # | Condition | What it models | Buildable now? |
|---|---|---|---|
| 1 | Missing footprint entry | agent will touch a file it didn't declare | **Yes** — `fp_drop`, already measured (§8d) |
| 2 | Overly broad footprint | agent declares a file it won't touch | **Yes** — `fp_add`, already measured (§8d) |
| 3 | Symbol-level misprediction | right file, wrong function/symbol within it | **No** — needs symbol-granularity footprint metadata per ticket and a scheduler/`nool_gated` variant that gates on symbols, not files; corpus and harness both need new code |
| 4 | Agent expands scope mid-execution | the agent's actual diff exceeds its declared footprint, discovered only during the run | **Partially** — the *passive* version (mine already-collected `nool_gated` transcripts for tickets whose real diff exceeded their declared footprint, as happened once uncontrolled at `t30`, §6b) is analysis, not a new run, and is cheap; the *deliberate* version (a corpus ticket whose spec undersells its true scope, in the spirit of the Specification Gap citation already in [§3](#sec-3).2) needs new ticket authoring |
| 5 | Cross-file semantic incompatibility with disjoint footprints | two tickets touch *different* files that must stay behaviorally consistent | **No** — the only semantic-incompatibility case in this corpus so far (the billing.go cluster, §6f) has all tickets sharing one *declared* footprint; a disjoint-footprint version needs new corpus tickets designed around a real cross-cutting invariant |
| 6 | Stale intent — a dependency changes after this ticket announced but before it lands | the footprint was accurate at announce time and became wrong mid-flight | **No** — needs timing-based fault injection in the dispatch loop (deliberately interleaving one ticket's completion after another's already-admitted change lands), a real harness capability gap, not a corpus change |

Conditions 1–2 at ≥5 reps (8e-i above) are the immediate, fully-costed
next step. Conditions 3, 5, and 6 each need dedicated harness/corpus
engineering before any prediction can be pre-registered against them;
condition 4's passive half is available today from existing data and
should be attempted before the deliberate half is built. None of 3–6 is
pre-registered by this section — this is a scoping proposal, not a
committed design, and predictions for each must be written before their
own data exists per this suite's standing discipline.

**Working thesis this battery would test, if built**: git-style
scheduling requires accurate upfront knowledge of what a change touches;
nool's coordination remains safe further into the territory where
agents are still discovering what the change is, rather than already
knowing it. §8d-i's four measured points (§6d–§6h) are consistent with
this thesis. They do not establish it, and replicating conditions 1–2
further does not by itself generalize to conditions 3–6 — each
remaining condition is a distinct claim requiring its own evidence, not
an extrapolation from the two already measured.

**8e-iii — natural, agent-discovered footprints (the "no-oracle"
condition, formerly 8d-ii above).** The most direct test of the working
thesis removes the oracle-plus-noise scaffold entirely: instead of
perturbing a known-correct declaration, let each arm's scheduler work
from a footprint the agent itself infers while actually solving the
ticket (git-side: static analysis or an LLM-predicted footprint feeding
the identical scheduler; nool-side: whatever native inference nool
exposes, if any, feeding `announce intent`/`discover conflicts`). If the
same widening-gap curve appears under real, uncontrolled uncertainty
rather than synthetic noise, it becomes substantially harder to dismiss
as benchmark engineering — this is judged the single most valuable
remaining experiment in this line, ranked above further ladder scaling
and above 8e-ii's conditions 3/5/6. It also requires the most new
harness code of anything proposed here (a footprint-inference step for
at least one arm) and is not scoped in detail in this section.

<a id="sec-8f"></a>
## 8f. Track D — model-generalization replication at N=25: Claude Fable 5.1 on nool 7.1.0 (pre-registered 2026-09-04, before any Fable data)

**Motivation.** Every LLM-in-the-loop Track D result in this suite rests
on one pinned model, `claude-sonnet-5` (the only exceptions — a
single-rep Gemini/Antigravity pair and a `limit=3` opencode trial — carry
no evidence weight). H7 (portability) is therefore untested for the
fleet track: the §8d/§8e-i reading — `nool_gated` degrades more slowly
than the identically-gated `git_scheduled` as declared footprints get
worse — could be a property of how one particular model follows,
violates, and recovers from footprint declarations rather than of the
coordination layer. A second model of a different tier and agentic
profile (Fable 5.1: always-on thinking, longer turns, different
tool-call density, 5× the per-token price) is the most direct way to
find out. Two other things change with it and are disclosed as part of
the condition, not controlled away: the product version advances to
nool 7.1.0 (unmeasured; the last measured is 7.0.3), and N=25 is a
ladder rung with sonnet data for `git_fleet`/`nool_fleet`/`nool_try`
but none for this arm pair (sonnet's `nool_gated`/`git_scheduled` data
sits at N=20 and N=35–45).

**Design.** Fixed factors: harness `claude` (Claude Code CLI 2.1.260,
`--setting-sources project,local`, `max_turns=30`, 600 s per agent —
the harness defaults, unchanged); model `claude-fable-5-1` (pinned;
`model_reported` recorded per agent from the CLI's own init event);
nool 7.1.0 (`git_sha b5387e65`); corpus
`tasks/fleet_service/tickets_v3.json` as it currently stands (`v3.1`,
60 tickets, tier `all`, starter pinned by `STARTER_SHA256`); protocol
`protocols/fleet_v4.json` (sha256 `1524b208…`); N=25 workers; arms
`nool_gated` vs `git_scheduled` — the v4 mechanism pair and the pair
behind every §8d/§8e-i point, chosen over the v4 primary control
`git_competitive` so that exactly one thing changes relative to the
sonnet evidence (the model), not a never-measured arm and a new model at
once. Two cells:

| Cell | fp_drop | fp_add | reps/arm | fp-noise seed (shared across arms within a rep) | shuffle seed (`--seed`, shared across arms within a rep) |
|---|---|---|---|---|---|
| zero-noise anchor | 0 | 0 | 3 | — | 25001 / 25002 / 25003 |
| very-heavy | 0.5 | 0.5 | 3 | 2501 / 2502 / 2503 | 25011 / 25012 / 25013 |

The very-heavy cell (half of every declared footprint wrong) is where
sonnet's gap was largest and hence the most detectable at n=3; the
zero-noise anchor establishes whether Fable honors declared footprints
at all and is the matched baseline the degradation is measured from.
Light and heavy cells are not included (cost — below). Each rep is one
invocation running both arms back-to-back on identical perturbed
footprints and identical ticket order:

```
python3 harness/fleet_run.py --harness claude --model claude-fable-5-1 \
    --workers 25 --tickets tickets_v3.json --arms nool_gated,git_scheduled \
    --reps 1 --seed <shuffle> [--fp-noise-drop 0.5 --fp-noise-add 0.5 --fp-noise-seed <fp>]
```

Unlike every prior cell, the ticket-order shuffle seed is pinned (prior
runs left it random and recorded `shuffle_seed: null`); pinning it makes
the two arms' paired comparison exact on the harness side and each run
re-runnable with the same ticket order and the same perturbation.

**Execution order and budget rule (fixed now).** Runs execute strictly
sequentially, one arm at a time, in this order: anchor rep 1 →
very-heavy rep 1 → very-heavy rep 2 → anchor rep 2 → very-heavy rep 3 →
anchor rep 3 — so that, if the budget rule stops execution early, the
informative cell reaches n=3 before the anchor does and neither cell is
ever more than one rep ahead of the other. Fable 5.1 is priced at 5×
sonnet-5 per token ($10/$50 vs $2/$10 per MTok); a one-turn headless
preflight call cost $0.17 (sonnet-equivalent ≈ $0.035). At the observed
$7.5–9.9 per sonnet run, each Fable run is expected to cost ~$35–45 and
the full 12-run plan ~$420–540. **Spend cap: $450 of recorded
`cost_usd`.** Before each invocation, if cumulative recorded spend plus
twice the mean cost of the completed runs would exceed the cap, execution
stops. A cell left below 3 reps is reported as budget-censored with the
runs it did get, never as an arm outcome; both cells are analyzed at
whatever n they reached, and the cross-cell comparison uses the paired
reps only. The RAM watchdog script covers only `git_fleet`/`nool_fleet`;
this arm pair already ran at N=35–45 on this same 16 GB machine without
incident (paper §5.9), so N=25 runs unguarded, with free memory sampled
by the operator and reported informationally. A run that dies for an
infrastructure reason (rate limit, session limit, OOM) writes no record,
is re-run with the same seeds, and the loss is logged under the existing
`invalidated_*` convention. Runs land one record at a time as they
finish; nothing is analyzed until a cell has all of its paired reps.

**Reference points (sonnet-5, already collected, quoted so the
predictions are checkable against fixed numbers).** Zero noise, this
arm pair, v3.1, N=20/35: `nool_gated` ≥59/60 in 4/4 runs,
`git_scheduled` ≥59/60 in 5/5, zero integration conflicts in all nine;
one `git_scheduled` zero-noise run ended with a failed final smoke test
despite 60/60 (the §6f `t10` event). Very-heavy (0.5/0.5), N=20–45, nine
paired reps: `nool_gated` 482/540 (89.3%), `git_scheduled` 444/540
(82.2%), pooled gap +7.0 pp; per-N mean gaps 6.7 (N=20), 2.5 (35), 5.0
(40), 11.7 (45) pp; `nool_gated`'s conflict count strictly below
`git_scheduled`'s in 7 of 9 pairs (one tie); `nool_gated`'s
`wasted_cost_usd` below `git_scheduled`'s in 7 of 9 pairs; conditional
acceptance ≥98% in 16 of 18 runs (two `git_scheduled` very-heavy runs
at 87–90%); final health green in all 18. Per-agent, zero noise (540
sonnet agents): median 7 turns (mean 8.9), median $0.128, median 27 s.

**Predictions (falsifiable, recorded before any Fable data):**
1. **Anchor.** In every zero-noise rep both arms accept ≥58/60 with
   zero integration conflicts, and the paired difference is within ±2
   tickets — Fable 5.1 honors declared footprints at least as well as
   sonnet, and at perfect information the arms remain indistinguishable
   (the §8c policy-not-tool result carries over to a second model).
2. **Direction (primary).** At very-heavy noise the paired mean
   acceptance of `nool_gated` exceeds `git_scheduled`'s (mean of the
   paired differences > 0), and `nool_gated`'s integration-conflict
   count is strictly lower than `git_scheduled`'s in at least 2 of the
   3 pairs.
3. **Magnitude.** The mean very-heavy gap lies in [+2, +12] pp — the
   same order as sonnet's per-N range (2.5–11.7 pp). Below +2 pp
   (including any reversal) the effect is judged materially
   model-dependent; above +12 pp it is larger on Fable than at any
   sonnet point and the mechanism question (§8e) sharpens rather than
   closes.
4. **Conditional acceptance** (accepted given landed) stays ≥95% pooled
   per arm within each cell; single-run dips (sonnet saw 87–90% in two
   `git_scheduled` very-heavy runs) are reported with the
   landing-commit diagnosis rather than averaged away.
5. **Wasted spend.** `nool_gated`'s `wasted_cost_usd` is at or below
   `git_scheduled`'s in at least 2 of the 3 very-heavy pairs.
6. **Cost calibration (secondary, not an arm claim).** Every Fable run
   records `cost_usd` in [$20, $70], and Fable's median per-agent turn
   count at zero noise is at or below sonnet's 7. Recorded to calibrate
   future budgeting on this model tier.

**Decision rule.** H7 (portability) is *supported for the §8d reading*
if predictions 1, 2 and 3 hold: the noise-robustness advantage is then a
property of the coordination layer that survives a change of model, and
the findings/paper wording moves from "measured on one model" to
"replicated on two models of different tiers". If 2 fails (mean gap ≤
0), the §8d/§8e-i advantage is re-labeled sonnet-specific until a third
model says otherwise, and the paper's generality wording is downgraded
accordingly. If 1 fails for one arm only, the run is reported with its
failure taxonomy and the cell is still analyzed. If the budget rule
stops execution with fewer than 2 paired reps in the very-heavy cell,
no direction claim is made in either direction. Three paired reps per
cell meets this suite's "3+" convention for a minimally powered
directional read, not a confirmatory one; run-level inference uses
`analysis/summarize.py`'s exact permutation test per cell, and the
cross-model comparison (Fable N=25 vs sonnet N=20–45) is descriptive
only, since N differs and the frozen protocol forbids pooling across
model strata.

**Out of scope, stated so it is not read in later:** `git_competitive`
(the v4 primary control, unmeasured with any LLM and deliberately not
confounded with a model change here), light/heavy noise cells, the
`ambiguous` tier cut, any N other than 25, and any Track B/C re-run on
Fable.

<a id="sec-8g"></a>
## 8g. Track D — native-planner arm: `nool_planned` (pre-registered 2026-09-06, before any 8g data)

**Motivation.** Three separate threads in this document converge on the
same gap. §8c's implementation audit established that the arm named
`nool_fleet` does not use nool to dispatch: admission is a Python
set-intersection over corpus-declared footprints, and `announce intent` /
`discover conflicts` run only after admission is already decided, their
output recorded but never consulted. §8b designed a condition exercising
nool's own `fleet plan` disjoint waves; it was never implemented. §8e
lists six candidate mechanisms for §8d's correlation and discriminates
among none of them, and its mechanism 1 — nool_gated's live
announce/release loop "behaves differently under load than the harness's
static footprint-intersection scheduler" — is precisely a claim about
*whose scheduler is on the critical path*. In every arm collected to
date, the answer is: ours. No result in this suite has ever exercised
nool's own scheduler. This arm changes that and nothing else.

**What the arm is.** `nool_planned`: before dispatch, the harness computes
the wave partition by calling `nool fleet plan --task <id>=<footprint>
--width <N> --json` once, then dispatches strictly wave by wave with a
barrier between waves. Integration is `nool merge`, as in
`nool_fleet`/`nool_gated`. Agents, prompt, model, worker slots, agent
timeout, launch stagger, acceptance scoring, and the pinned starter SHA
are the §8a values, unchanged. `fleet plan` without `--run` is a
preview-only planner: it spends nothing, launches no agent, and requires
no ledger state beyond an initialized repo.

**Measured before any run** (2026-09-06, nool 7.2.0, scratch ledger, the
live `tasks/fleet_service/tickets_v3.json` footprints, exit 0, zero
spend):

| `--width` | tickets | waves | wave sizes |
|---|---|---|---|
| 8 | 60 | 10 | 8, 8, 8, 8, 8, 8, 8, 2, 1, 1 |
| 25 | 60 | 10 | 25, 7, 6, 7, 5, 5, 2, 1, 1, 1 |

The long tail at `--width 25` is the contended clusters serializing —
the mechanism under study — and confirms the planner produces a usable,
non-degenerate partition on the real corpus rather than one wave per
ticket.

**What it discriminates.** The suite currently varies the integration
verb but holds the scheduler fixed. Adding this arm completes the
factorial:

| | harness scheduler | nool `fleet plan` |
|---|---|---|
| `git merge` | `git_scheduled` | `git_planned` (ablation, below) |
| `nool merge` | `nool_fleet` | `nool_planned` (this arm) |

`nool_planned` vs `nool_fleet` isolates the scheduler with the
integration verb held constant; `nool_planned` vs `git_planned` isolates
the integration verb with nool's scheduler held constant. Together they
answer the §8c attribution question — how much of the effect is product
and how much is the policy we wrote — for the dispatch half, which §8c
left open.

**A confound, disclosed now rather than discovered later.** nool's
planner is wave-partitioned with a barrier: every task in wave k finishes
before wave k+1 starts. The harness's footprint scheduler is
rolling-greedy: a ticket is admitted the moment its footprint stops
intersecting the in-flight set. These are different scheduling
disciplines independent of how disjointness is computed, and a barrier
alone changes both wall time and the merge queue's input distribution.
A `nool_planned` effect is therefore attributable to nool's planner *as a
whole* — disjointness computation and wave discipline together — and not
to the disjointness computation alone. Isolating those two would need a
third arm running the harness's own disjointness with a barrier imposed;
it is named here as a known unresolved layer, not run.

**The `git_planned` ablation.** Identical nool-computed waves, `git merge`
integration, no nool anywhere in the arm's workspace. The waves are
computed in a scratch ledger outside the arm's workspace and passed in as
data, so §8a's contract that "the git control arm must have no
coordination substrate at all" — machine-enforced by `setup_ws`'s
assertion that no `.nool` directory exists — holds unchanged. This
mirrors exactly how `git_scheduled` reuses `nool_fleet`'s scheduler.

**Design.** Fixed factors: harness `claude`, model `claude-sonnet-5`
(pinned — this arm changes the scheduler, so it must not also change the
model; §8f's Fable condition is a separate stratum and the frozen
protocol forbids pooling across model strata); corpus
`tasks/fleet_service/tickets_v3.json` (`v3.1`, 60 tickets, tier `all`,
starter pinned by `STARTER_SHA256`); protocol `protocols/fleet_v4.json`
(sha256 `1524b208…`); **N=35 workers** — see the amendment note below.
Zero footprint noise: this arm is about the
scheduler, and §8d's noise dimension is deliberately not crossed with it
in the first cell. Arms `nool_planned`, `git_planned`, and `nool_fleet`
(the incumbent comparator, re-run in the same batch rather than compared
against older reps, so machine state and nool version are shared), 3 reps
each, ticket-order shuffle seed pinned and shared across arms within a
rep: 27001 / 27002 / 27003.

```
python3 harness/fleet_run.py --harness claude --model claude-sonnet-5 \
    --workers 35 --tickets tickets_v3.json \
    --arms nool_planned,git_planned,nool_fleet --reps 1 --seed <shuffle>
```

**Amendment, 2026-09-06, before any 8g data exists: N=25 → N=35.** This
section was pre-registered hours earlier at N=25, on the reasoning that it
was the rung with the most sonnet comparators. The operator directed N=35
instead, and the change is recorded here rather than applied silently. It
is a legitimate amendment and not a moved goalpost for one reason only:
**zero 8g runs have been collected**, so no result exists that this choice
could have been selected to favor. If any 8g data had been in hand, the
honest move would have been a new cell, not an edit. What the change buys:
N=35 is the rung where §8c's own re-analysis found git's failure mode
turning bimodal (37/60 and 20/60 across two reps, the second a near-total
build poisoning), so it is the rung where a scheduler difference has the
most room to show; `nool_fleet` also has 5 sonnet reps at N=35 on corpus
v3 against 2 at N=25. What it costs: the measured `--width 25` partition
in the table above (10 waves, tail 2/1/1/1) is the one with a
demonstrated non-trivial tail; at `--width 35` the partition is recomputed
per run and recorded in `plan.wave_sizes`, so if it degenerates toward
one wide wave plus a long tail of singletons, prediction 3's wall-time
reasoning changes and that must be read off the recorded plan rather than
assumed. N=35 has run unguarded on this 16 GB machine without incident
(§8f, paper §5.9), so no watchdog.

Runs execute strictly sequentially, one arm at a time, in rep-major order
so all three arms of rep 1 complete before rep 2 begins; if the budget
rule stops execution early, whole reps are complete rather than one arm
being three reps ahead. **Spend cap: $90 of recorded `cost_usd`** at the
observed $7.5–9.9 per sonnet run for 9 planned runs — unchanged by the
amendment, since N is worker concurrency and the ticket count (60) that
drives token spend is identical. A cell left below 3 reps is reported as
budget-censored with the runs it got, never as an arm outcome.

**Predictions (falsifiable, recorded before any data).**
1. `nool fleet plan` returns a partition whose waves are pairwise
   footprint-disjoint under the corpus-declared footprints in every rep —
   i.e. it computes at least what the harness scheduler computes. A
   failure here is a product finding and is reported as one.
2. `nool_planned` accepts within ±2 tickets of `nool_fleet` at N=35,
   whose sonnet anchor on corpus v3 is 60/60 in four of five collected
   reps and 59/60 in the fifth — and within ±2 of the `nool_fleet` reps
   run in this same batch, which is the comparison that actually controls
   for machine state and nool version. The scheduler is being swapped for
   one solving the same problem; a large gap means the two disagree about
   disjointness, which prediction 1 says they should not.
3. `nool_planned` wall time exceeds `nool_fleet`'s by ≥20%, from the
   barrier: the measured `--width 25` partition serializes into 10 waves
   whose last four hold one or two tickets each, so the run cannot finish
   faster than the sum of ten wave latencies.
4. `git_planned` accepts strictly fewer tickets than `nool_planned`, with
   the shortfall being merge conflicts on contended clusters — the same
   signature `git_scheduled` shows against `nool_fleet`. If instead
   `git_planned` matches `nool_planned`, the dispatch discipline, not the
   integration verb, is carrying the effect, and §8c's product attribution
   narrows sharply.

**Decision rule.** The arm supports "nool's own scheduler reproduces the
policy result" if predictions 1 and 2 both hold; it falsifies it if
`nool_planned` accepts ≥5 tickets fewer than `nool_fleet` while
prediction 1 holds, which would locate the loss in the wave discipline
rather than in disjointness. Prediction 3 failing (no wall-time cost)
is reported as a favorable surprise, not as support for anything else.
Prediction 4 is the §8c attribution read and is reported whichever way it
goes; with 3 reps it is a directional read under this suite's own "3+"
convention, not a confirmatory one, and run-level inference uses
`analysis/summarize.py`'s exact permutation test.

**Blocking precondition (nool 7.2.0, found 2026-09-06).** On nool 7.2.0
the governed profile's `[steer]` pre-solidify architect trigger
(`coupling_slope_gt = 0.3`) fires on `nool try promote` and halts it with
"Steering intervention required at PreSolidify" *after* the Ghost-Run
reports full validation passed. Scripted-adapter validation puts
`nool_try` at 3–4 of 8 where 7.0.0/7.0.1 gave 8/8 and 60/60. This arm
does not use try branches — `fleet plan` is invoked as a planner only and
integration is `nool merge`, which does not trip the gate — so 8g is not
blocked by it. It is recorded here because any 8g run batch that also
re-runs `nool_try` would be contaminated, and because the same gate would
apply if a later condition used `fleet plan --run`, whose isolation is
implemented with try branches and `try promote`. The gate must be
resolved, or held constant across every nool arm, before any try-based
arm is run again on 7.2.0 or later.

**Out of scope, stated so it is not read in later.** `nool fleet start` —
nool's builder/reviewer quorum driving the agents themselves — remains
out of scope exactly as §9 says. It would replace this suite's pinned
Claude Code agent with nool's own harness backends and its own prompts,
breaking the model and prompt parity every arm holds constant; it tests a
different claim and needs its own condition, not this one. Also out of
scope: any N other than 25, footprint noise crossed with this arm, the
`ambiguous` tier cut, and any model other than `claude-sonnet-5`.

<a id="sec-8h"></a>
## 8h. Governance-profile parity correction (architect decision, 2026-09-06, prospective-only)

**The rule, fixed before the change.** A control belongs in the nool arms'
governance profile only if the git arms' control set contains a functional
counterpart. This is the operational form of §8a's existing contract, which
`setup_ws` states as "the rules are held constant; only the enforcement
substrate differs" — a rule about *rules*, which is violated when one side
carries a live blocking control the other has no analogue for, however
faithfully the documentation is mirrored.

**Applying it.** The git arms receive `ci.yml` required checks (build and
test), `CODEOWNERS`, `POLICY.md`, `.pre-commit-config.yaml`, and the
harness's symmetric secret gate. Every one of those is either automatic or
inert documentation: nothing in the git arms halts work pending a named
human role's approval, because there are no pull requests and no reviewers
in this harness. `nool_governed.toml` declared two interactive steering
checkpoints — a CISO `pre-push` approval on sensitive paths and an Architect
`pre-solidify` approval on `coupling_slope_gt = 0.3`. Neither has a
counterpart. **Both are removed; `[steer]` is set to `enabled = false`.**
Every automatic gate is kept unchanged: the blast-radius airlock
(`blast_block_threshold`), the Aram policy gate, invariants, reification,
and the shared secret scan.

**Why not the alternatives**, recorded so the choice is auditable:
- *Auto-approving the checkpoint from the harness* (`nool steer --action
  approve`) would have the harness grant itself Architect authority. That
  measures a product configured to defeat its own control, and the git arms
  have no counterpart to that either — it replaces one asymmetry with a
  worse one.
- *Censoring steer-halted tickets from the denominator* is invalid here.
  The trigger is `coupling_slope_gt`, which correlates with the
  contended-cluster tickets this study is about; dropping halted tickets
  would preferentially remove the hardest ones and inflate the arm. Where a
  steering halt does occur it disqualifies the **run**, never the ticket.
- *Keeping the gate and scoring halts as rejections* scores nool against a
  blocking control `git_scheduled` and `git_competitive` never face.

**Prospective-only; no collected number moves.** There are zero steering
halts anywhere in `results/trackc/fleet_runs.jsonl` — the pre-solidify point
was inert on every run ever collected. The old profile and the new one are
therefore behaviorally identical over all existing data, and no result
requires re-collection. What changes is the recorded
`governance_profile_sha`, from
`4e94f9c0a176e268f52024b38da57937b8f0d44fcd5acbb1e84bf9a0c96f2355` to
`e551b88ae96ecf88e41554d02a1b0e78f64be03b12bcaa301e70f8f00dbcb8b1`, so any
reader can partition runs by profile without trusting this note.

**Disclosure of direction.** Removing a gate only the nool arms faced
removes a handicap from nool, and this document's convention is to say so
rather than let a reader discover it. The justification is the parity rule,
which was fixed before the change and is symmetric: if the git arms ever
gain a real approval gate — a required human review that actually blocks —
nool's steering checkpoint returns with it.

**The product finding this came out of, reported separately.** Under nool
7.2.0 the `pre-solidify` steering point fires on `nool try promote` — after
the Ghost-Run reports full validation passed — but does not fire on `nool
merge`. The same declared policy therefore binds one landing verb and not
another. Measured on the scripted adapter at N=8, corpus v1: `nool_try`
3/8 with five tickets held at `PreSolidify`, against 8/8 for
`nool_fleet` and `nool_gated` on the identical profile and tickets, and
against `nool_try`'s own 8/8 and 60/60 on nool 7.0.0/7.0.1. This is a
non-uniform-enforcement finding about the product, not the reason for the
parity correction above, and the correction is not a workaround for it —
the parity argument holds independently and held before 7.2.0 made the gate
visible. After the correction all three nool arms return 8/8 on the same
scripted check.

**Permanent tripwire.** `fleet_run.py` classifies any steering halt as
`rejection_kind: "steer"` (distinct from `validation` and `coordination`),
counts it in the run summary as `steer_blocked`, and prints an explicit
warning that the run is not a clean arm outcome. A future profile or product
change that reintroduces a steering halt is therefore loud rather than
silently scored as a validation failure, which is how this one was
originally mislabeled.

<a id="sec-8i"></a>
## 8i. Track D — version replication of the very-heavy-noise cell on nool 7.2.0 (pre-registered 2026-09-06, before any 8i data)

**Motivation.** The noise dose-response is this suite's strongest and
most-replicated separation, and **none of it has ever run on the installed
product version.** Every noise cell was collected on nool 7.0.1 (the N=20
light/heavy/very-heavy ladder, 2026-08-27) or nool 7.0.3 (very-heavy at
N=35/40/45, 2026-09-01); the installed CLI is 7.2.0. The only 7.2.0 Track D
data in existence is §8g's zero-noise cell, which sits at an acceptance
ceiling and discriminates nothing.

Two facts bracket how much this matters, and both are recorded rather than
assumed. Track B re-ran clean on 7.2.0 the same day (§ results/micro, every
qualitative outcome across b1–b7 identical to 7.1.4, including the merge and
concurrency mechanisms a fleet run leans on). But a real fleet-level 7.2.0
regression was also found that day — the `[steer]` pre-solidify gate began
firing on `nool try promote`, taking `nool_try` from 8/8 to 3/8 (§8h) — and
Track B did not catch it, because it is a governance interaction rather than
a mechanism. "Track B replicates" is therefore not evidence that the fleet
arms replicate, and this condition exists to test the fleet arms directly.

**Cell choice.** `d0.5/a0.5` at N=45, `nool_gated` vs `git_scheduled`. This
is the cell where the collected separation is largest and the two arms do
not overlap at all — `nool_gated` 56/56/55 against `git_scheduled` 52/45/49,
mean gap +7.0 tickets — so it is where a version regression in either
direction would be most visible. A cell with overlapping ranges could absorb
a real regression inside its own spread.

**Design.** Fixed factors: harness `claude`, model `claude-sonnet-5`
(pinned, matching the cell being replicated); corpus
`tasks/fleet_service/tickets_v3.json` (`v3.1`, 60 tickets, tier `all`,
starter pinned by `STARTER_SHA256`); protocol `protocols/fleet_v4.json`
(sha256 `1524b208…`); N=45 workers; `--fp-noise-drop 0.5 --fp-noise-add
0.5`; arms `nool_gated` and `git_scheduled`; 3 reps. **The footprint-noise
seeds are reused from the cell being replicated — 4501 / 4502 / 4503,
shared across arms within a rep** — so every arm in both batches sees a
bit-identical footprint perturbation and the version is the thing that
varies.

```
python3 harness/fleet_run.py --harness claude --model claude-sonnet-5 \
    --workers 45 --tickets tickets_v3.json \
    --arms nool_gated,git_scheduled --reps 1 \
    --fp-noise-drop 0.5 --fp-noise-add 0.5 --fp-noise-seed <4501|4502|4503> \
    --seed <45001|45002|45003>
```

**Two disclosed differences from the 7.0.3 batch**, neither controlled away:

1. *Ticket order.* The 7.0.3 runs left `--seed` unset and recorded
   `shuffle_seed: null`, so their ticket order was random and is not
   recoverable. No exact match is possible. This batch pins 45001 / 45002 /
   45003 so it is reproducible going forward. Three arbitrary pinned orders
   and three arbitrary random orders are the same draw statistically at
   n=3; the difference is that this batch can be re-run and that one
   cannot.
2. *Governance profile.* `nool_governed.toml` changed today under §8h's
   arm-parity rule, `4e94f9c0…` → `e551b88a…`. It is argued inert **for this
   arm pair specifically**: `nool_gated` integrates with `nool merge`, the
   removed steering points never fired on that path, and there are zero
   steering halts anywhere in `results/trackc/fleet_runs.jsonl`. Prediction
   4 below turns that argument into a falsifiable check rather than leaving
   it as an assertion. `git_scheduled` never applies the profile at all.

**Execution and budget.** Strictly sequential, one arm at a time, rep-major
(both arms of rep 1 before rep 2). At the replicated cell's observed mean of
$7.73/run, six runs project to ~$46. **Spend cap: $60 of recorded
`cost_usd`.** Before each invocation, if cumulative spend plus twice the
mean cost of completed runs would exceed the cap, execution stops; a cell
below 3 reps is reported as budget-censored with the runs it got, never as
an arm outcome. N=45 has run unguarded on this 16 GB machine (paper §5.9),
so no watchdog.

**Predictions (falsifiable, recorded before any data).**
1. `nool_gated` accepts 53–58 in every rep — its 7.0.3 band (55–56)
   widened by ±2 for run-to-run variation.
2. `git_scheduled` accepts 43–54 in every rep — its 7.0.3 band (45–52)
   widened by ±2.
3. The paired gap `nool_gated − git_scheduled` is positive in all three
   reps, with a mean within ±3 of the replicated +7.0. This is the
   replication claim proper; 1 and 2 locate any failure to an arm.
4. Zero `steer_blocked` in every `nool_gated` run. This is §8h's inertness
   argument made falsifiable: a non-zero count means the profile change was
   not inert for this arm after all, and the run batch is confounded and
   reported as such rather than as a version result.

**Decision rule.** The replication holds if predictions 1–4 all hold. If
prediction 3 fails while 1 and 2 hold, the effect size moved without either
arm leaving its band, and the honest report is "gap not replicated at n=3"
rather than a regression claim. If `nool_gated` falls below 53 while
`git_scheduled` stays in band, that is a **7.2.0 product regression** and is
reported as a product finding with the same weight §8h's steering finding
received — not quietly absorbed into the noise ladder. If both arms drop
together, suspect the corpus or the machine before the product, and check
`final_health` and `t21` behaviour before drawing any conclusion. At n=3
this is a directional read under this suite's own "3+" convention, not a
confirmatory one; run-level inference uses `analysis/summarize.py`'s exact
permutation test.

**Outcome (2026-09-06/07): rate-limit censored at one paired rep.** Rep 1
completed both arms; rep 2 completed `nool_gated` then `git_scheduled` aborted
on the operator account's provider rate limit; rep 3 aborted at its first arm.
The harness wrote no record for either aborted run. Under this section's own
rule the cell is reported as censored, and no direction claim is made. What the
completed runs show, reported as observations: on fp-seed 4501 both arms moved
by exactly minus five tickets against their 7.0.3 values (56 to 51, 52 to 47)
and the paired gap replicated exactly at +4, which is the both-arms-drop case
the decision rule attributes to a shared cause rather than the product; on
fp-seed 4502 `nool_gated` returned 57 against 56, in band, so the rep 1 shift
did not recur. Prediction 4 held in every 7.2.0 run (`steer_blocked` = 0),
verifying §8h's inertness argument. One nool-specific product finding stands
independent of the censoring: `nool merge` on ticket t47 in rep 1 failed with
"SQLite error: database is locked", exit 1, a failure mode the git arm cannot
exhibit and which the 7.0.3 runs on the same seed did not (ledger `76af4310`).
The two missing runs remain owed to this section under the same seeds.

## 9. Out of scope (this iteration)

Nool fleet/orchestration as the multi-agent driver (tests a different claim —
noted as future condition), knowledge-ledger carryover (Tier 3), human-developer
baselines, cross-repo enterprise simulations.

Clarification (2026-09-06, on adding §8g): "as the multi-agent driver" is the
operative phrase and still holds — `nool fleet start`, in which nool's own
builder/reviewer agents replace this suite's pinned Claude Code agent, stays
out of scope. §8g uses `nool fleet plan` as a *scheduler* only, with the
agents unchanged, which is a different surface and is in scope.
