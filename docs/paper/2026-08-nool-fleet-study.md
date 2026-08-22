# Benchmarking a Coordination Layer for Autonomous Coding-Agent Fleets: A Pre-Registered Empirical Study of Nool versus Git

**Arun Balakrishnan** — Nool, Inc. (arun@nool.dev)
**Status:** Phase 1 report (mechanism suite + pilot-scale product experiments). 2026-08-20.
**Disclosure:** This is a vendor-run evaluation of the vendor's own product, mitigated by pre-registration, negative controls, committed raw data, and a replication package. Read §7 before the results.

## Abstract

Enterprises considering fleets of autonomous coding agents need evidence for an outcome claim: that without a coordination layer, sufficiently agentic development becomes measurably unsafe or expensive, and that a coordination layer materially reduces those failures. We present a pre-registered benchmark suite comparing Nool — a semantic-agentic version-control and coordination system — against plain git across three instrument families: seven deterministic mechanism benchmarks (B1–B7), a 2×2 LLM-in-the-loop product experiment (single/multi agent × git/nool; N=5 per cell, one pinned model), and a fleet-operations pilot (5 concurrent real agents, 8-ticket backlog with designed contention). All outcome scoring is on final-system state (hidden acceptance tests, main-branch health), never on tool warnings. Phase 1 results are mixed and instructive: nool provides measured wins in concurrent-write attribution (90/90 ops attributed 1:1 vs 64% commingled under git at 15 writers), context-retrieval economy (163 vs 660 bytes to a correct hit), and syntax-level commit gating (Phase 1 exercised only the `--fast` relaxed path; see below); it currently provides no measured advantage in file-level merge outcomes (identical to git across three scenarios despite its semantic layer correctly classifying changes as commutable), fails to preserve unrelated later work during selective undo (fixed in 6.14.1), and mislocalizes regressions in its bisect tool (fixed in 6.14.1). The 2×2 product experiment shows no arm separation at pilot power. Two subsequent developments, both under the same pre-registered goalposts, change the picture. First, a product release (nool 6.14.1) closed three of the four adverse mechanism bounds on re-test: contended merges now converge 15/15, selective undo preserves later unrelated work 5/5, and bisect names the true culprit; the fourth (B4 commit gating) was resolved by measurement rather than product change — the default governed path (`propose --solidify`, full validation) rejects the test-breaking change at propose, and the earlier negative had measured only the explicit `--fast` relaxed path, an attributable operator opt-in. Per-operation latency stays roughly 7–10× git. Second, a pre-registered scale-up of the fleet benchmark — 10 agents, 20 tickets with function-level contention clusters — produced the first clear arm separation: the uncoordinated git arm accepted 13/20 and 1/20 (in the latter rep a textually-clean merge silently broke the build, voiding 13 landed tickets), while the nool arm's footprint-gated dispatch accepted 19/20 in both reps with zero integration failures, at equal agent spend and +40–70% wall time. A subsequent scale-up to N=25 workers first hit an infrastructure ceiling rather than a product one — it reproducibly exhausted the operator machine's memory before any agent work began — resolved by a launch-cadence fix to the harness, after which two further pre-registered ladder points completed: at N=25, nool accepted every ticket with zero merge conflicts in both reps (60/60) while git failed roughly a third of contended tickets to merge conflicts each rep (41/60, 40/60); at N=35, nool again reached 60/60 with zero conflicts in both reps while git's failures deepened with concurrency — one rep merged cleanly but failed tests package-wide (37/60), the other suffered a full build-poisoning event that voided most of the backlog (20/60) — showing the separation strengthening, not merely holding, as N climbs. A same-session corpus-integrity incident — stray ticket solutions landed directly against the benchmark's source template — was found and fixed before it could affect any reported result, and a mid-run operator account rate limit corrupted one repetition, which is reported and excluded rather than silently averaged in. We contribute the claim framework, the instruments, honest bounds that current mechanism behavior places on the enterprise claims, and a costed roadmap for the three decisive proofs: fleet correctness at high concurrency, longitudinal institutional memory, and deterministic governance.

## 1. Introduction

Coding agents are moving from single-session assistants to concurrent fleets operating on shared repositories. The systems question is no longer whether one agent can complete a task but whether N agents can do so without interfering, whether organizational decisions survive across agents and time, and whether the resulting system remains correct as history accumulates. Nool positions itself as the coordination layer — an "air traffic controller" — for such fleets.

This study evaluates that position empirically. Following the adoption logic that buyers purchase outcomes rather than mechanisms, we organize all measurement around five outcome claims (pre-registered as C1–C5): **C1** agents make better changes (final-task correctness); **C2** fleets stop interfering (conflict/regression/rework rates); **C3** decisions survive across agents and time (constraint preservation); **C4** concurrency scales safely (correctness at increasing N); **C5** cost per accepted change falls despite coordination overhead.

Contributions:

1. A pre-registered, reproducible benchmark suite (Apache-2.0) with three instrument families, committed raw data, and full per-run provenance.
2. Mechanism-level findings (B1–B7) that place quantitative bounds on the outcome claims — including three negative findings that constrain what the product can currently deliver.
3. Pilot-scale product experiments: a 2×2 agent-mode × VCS grid and a 5-agent fleet-operations benchmark scored on final-system state.
4. Two methodological incident reports: operator-environment contamination of agent sessions (detection, quarantine, and the isolation contract now required of all harness adapters), and a corpus-integrity incident in which ticket solutions were landed directly against the benchmark's source template (detection, fix, and the verification practice — diffing against the last pre-registration commit — now required before trusting any fleet run).
5. A costed roadmap for the three decisive proofs (P1 fleet correctness at scale, P2 longitudinal memory, P3 deterministic governance).

## 2. Related work

Long-horizon and evolution benchmarks — SWE-EVO (48 release-note-derived tasks; frontier ~25% vs ~73% on SWE-bench Verified) and RoadmapBench (115 version-upgrade tasks) — established that sustained multi-file development is far from saturated. SlopCodeBench measures degradation as agents iterate on their own code (erosion rises in 80% of trajectories), providing the natural instrument for our longitudinal claim (C3). CooperBench (652 two-feature conflict tasks) found two-agent cooperation roughly halves success versus one agent doing both features, and contributes the failure taxonomy (expectation/communication/commitment) we adopt. Two results shape our controls: the Specification Gap (integration success 58%→25% as spec detail drops) fixes specification detail per task across arms; Co-Coder shows partitioning strategy dominates multi-agent outcomes, so decomposition is task-authored and identical across arms. Our suite differs from all of the above in manipulating the *coordination substrate* under a fixed agent and fixed decomposition.

## 3. Study design

**Pre-registration.** Hypotheses (H1–H7), the claim framework (C1–C5), all track designs, and the analysis plan were committed to an append-only ledger and pushed to a public repository before the corresponding data was collected. The commit history is the audit trail.

**Instruments.**
- *Track B (mechanisms, deterministic):* seven benchmarks, no LLM, monotonic-clock timing, isolated throwaway workspaces, JSON results with provenance (versions, platform, timestamps). Free to replicate.
- *Track C (product, 2×2):* headless Claude Code sessions (model pinned to `claude-sonnet-5` in every cell; exact tokens/turns/cost from the CLI's own accounting — estimation banned) on a validated greenfield task with hidden acceptance tests; multi-agent mode uses task-authored decomposition into isolated worktrees, arms differing only at integration (`git merge` vs `nool merge`).
- *Track D (fleet pilot):* 5 worker slots, 8 tickets with designed footprint contention (three overlap clusters), identical prompts and model across arms. `git_fleet`: all tickets parallel, sequential merge queue. `nool_fleet`: tickets registered as nool tasks; dispatch gated by `announce intent`/`discover conflicts` over declared footprints; integration via `nool merge`. Scored on per-ticket hidden acceptance tests and main-branch build/smoke health after every merge.

**Controls.** Same pinned model everywhere; frozen prompts (hashed); identical tool allowlists; identical decomposition; spec-detail level fixed; timeouts and turn caps identical; per-run provenance (CLI versions, nool/git versions, model reported by the harness).

**Environment isolation (incident).** An initial Track C batch was invalidated when operator-level agent configuration leaked into benchmark sessions: transcripts showed an agent invoking an operator-installed skill whose rules require awaiting human design approval — unfulfillable headlessly — producing runs with 3–4 turns and zero file writes. The batch is quarantined verbatim with a written cause analysis; the adapter contract now mandates exclusion of user-level configuration (for Claude Code, `--setting-sources project,local`) while retaining project-level configuration, which in the nool arm *is* the treatment. We report this as a general validity requirement for agent benchmarking: the operator's own tooling is a contamination vector.

**Corpus integrity (incident).** Between the scale-up 2 pre-registration and all N=20/N=25 data reported in §5.5, five commits landed partial or complete ticket solutions directly against the live `tasks/fleet_service/starter/` corpus — the exact template every fleet worker copies verbatim at the start of every run — instead of going through the harness's throwaway-workspace flow. One of the five commits also bundled an unrelated adapter file under a misleading intent message, consistent with an overly broad stage-everything land operation. The incident was detected before any scale-up 2 data collection, by diffing `starter/` against the last pre-registration commit, and fixed by restoring the pre-contamination file contents and confirming that diff returns empty. No result in this report was collected against the contaminated corpus. We report the incident for the general practice it establishes: corpus purity does not self-evidence from an unexpectedly dirty working tree, because a version-control system that accepts plausible per-change commit messages can land contamination that reads as legitimate history. Every fleet run's `starter/` state should be diffed against its corpus's own pre-registration commit before the run, not merely checked for cleanliness.

## 4. Mechanism results (Track B)

All numbers below are medians from committed raw JSON (`results/micro/`); nool 6.13.0, git 2.50.1, macOS arm64.

**B1 — Overhead (C5 bound).** Per-event agent-hook latency: 8–19 ms across the five harness hooks nool installs. Landing a change: `propose --fast --solidify` 130 ms (1 file), 137 ms (10), 260 ms (100, via the sanctioned `--auto-justify` path — the blast-radius gate blocks wide non-interactive proposes without justification) versus git add+commit at 19–23 ms. Overhead is 6–13× git's but small in absolute terms relative to LLM latencies.

**B2 — Live concurrency (C2/C4).** N writers landing disjoint-file changes in one shared workspace, identical retry budgets. Git completes faster in wall time (1.05 s vs 3.94 s at N=15) and, with sweep-aware accounting, loses no work — but at N=15, 58 of 90 logical changes (64%) were swept into other writers' commits, yielding 32 commits for 90 changes: attribution destroyed. Nool landed 90/90 as 90 individually-attributed knots with zero retries, at per-op latency rising 109→409 ms with contention. The trade is speed versus attribution integrity; for audited environments the latter is the enterprise-relevant property.

**B3 — Recovery (C1 operational).** Removing a bad landing while keeping later unrelated work: `git revert` preserved the unrelated work in 5/5 repetitions (16.8 ms median). Nool's selective-undo (`pluck --execute`) removed the damage 5/5 but destroyed the later unrelated work 5/5 — in both a linear timeline and a thread-separated timeline — because pluck removes causal descendants and sequential proposes create causal dependency even across threads. **Negative finding:** as shipped, nool's selective undo is strictly worse than `git revert` for the fleet-recovery scenario tested.

**B4 — Guardrails (P3 bound): governance-mode semantics.** The benchmark tests three distinct governance paths:

1. **Default governed path** (`nool propose --solidify`, full semantic validation): runs project-level tests in a ghost-run. **Rejects** the test-breaking change at propose (test fails).
2. **Explicit relaxed path** (`nool propose --fast --solidify`, syntax-only + deferred validation): **Accepts** the test-breaking change — only AST precheck runs at propose; deferred `validate --all` passes with a warning that project integrity was not checked.
3. **Authority/control** (not tested here; Track F): whether organizations can restrict who invokes the relaxed path.

Git (control) accepts everything. Both nool paths reject the syntax-broken change at propose (AST precheck).

The key finding: **the default governed path catches semantic regressions**; the "unmoved bound" in prior reports reflected testing only the explicit relaxed path (`--fast`). The deterministic-governance claim (P3) is therefore not bounded at the default configuration — it is bounded at the *relaxed* configuration, which is an intentional operator opt-in. Track F will test configured enforcement including raw-git bypass and authority controls.

**B5 — Swarm merge (C2 bound).** Fifteen branches merged into main under three scenarios, success detected from working-tree state. Disjoint files (negative control): both arms 15/15 clean, 3/3 reps. Same-anchor and different-functions (the AST-mergeable case): both arms identically 1 clean / 14 conflicts, 3/3 reps each. Nool's SemanticMergeEngine reported semantic convergence for all 15 branches in both contended scenarios (correctly — the added methods are symbol-disjoint) while the file-level merge fell back to git's textual merge and conflicted identically. **Negative finding:** the semantic layer classifies but does not act; nool merge currently confers no file-level integration advantage over git. C2's killer metric (50%+ conflict reduction) is unreachable until this changes. *Setup audit:* `nool init` does install a git merge driver, correctly registered in every benchmark workspace — but scoped exclusively to nool's ledger artifacts (`.nool/knot.bin merge=nool-knot`, `.nool/manifest.toon merge=union`); source files carry `merge: unspecified`. The commutative merge machinery therefore converges the Knot DAG across branches, not working-tree source code — which is exactly the mechanism boundary this benchmark measures, and rules out harness misconfiguration as the explanation.

**B6 — Context retrieval (C1/C5 support).** In a 13-file repo built knot-by-knot with recorded intents, `query context file#symbol` reached the ground-truth function in 163 bytes vs 660 for the grep-then-read-files baseline (whole repo: 4,748); the realistic chained flow (semantic search → context) cost 408 bytes. A real economy at trivial repo scale; the roadmap re-measures at 50k-LOC scale where the claim becomes decisive.

**B7 — Regression localization.** Identical 13-landing timeline, culprit at landing 7, identical test command. `git bisect run` named the correct commit in 3 steps. Nool's `debug bisect` required an explicit `--bad` (its HEAD default errors) and then named landing 1 — the first post-good knot — consistent with the test not being executed against materialized historical states. **Negative finding:** nool's bisect currently loses to git's on its own claimed strength.

## 5. Product-level results

### 5.1 Track C — 2×2 grid (N=5 per cell, claude-sonnet-5)

| Cell | Hidden-test pass | Clean merges | Median turns | Median output tokens | Median wall | Cost (5 runs) |
|---|---|---|---|---|---|---|
| single_git | 5/5 | — | 7 | 4,904 | 50 s | $1.12 |
| single_nool | 5/5 | — | 6 | 4,873 | 48 s | $1.20 |
| multi_git | 5/5 | 10/10 | 32 | 13,739 | 157 s | $3.92 |
| multi_nool | 4/5 | 10/10 | 29 | 13,647 | 154 s | $3.74 |

No arm separation on any metric at this task difficulty and power; the analysis labels every comparison underpowered by design. The single failure is qualitatively informative: both branches merged cleanly, but the build broke on an inter-agent interface mismatch (one agent assigned to a field the other had exposed as a method) — CooperBench's "expectation failure," and a live example that clean merges do not imply working integration. Both layers are captured separately in the data.

### 5.2 Track D — Fleet-operations pilot (5 agents, 8 tickets)

| Metric | git_fleet | nool_fleet |
|---|---|---|
| Tickets accepted (hidden tests) | 8/8 | 8/8 |
| Integration conflicts | 0 | 0 |
| Main health after every merge | all green | all green |
| Wall time to backlog completion | 64 s | 74 s |
| Total agent cost | $1.53 | $1.49 |
| History entries on main | 16 commits | 18 commits + 10 knots |

Gated dispatch behaved as designed: the nool arm's merge order shows each
contention cluster serialized (t2→t5, t1→t6→t8, t3→t7; the disjoint t4
interleaved), at a coordination cost of ~10 s wall time (+16%) and no token
premium. But the pilot's decisive observation is about the baseline: the
uncoordinated git arm also completed 8/8 with zero conflicts — five real
agents editing overlapping files made textually compatible choices that our
scripted same-anchor stressor (B5) does not. At this scale and ticket size,
designed footprint overlap did not convert into baseline failures, so the
pilot validates the fleet instrument, the gating mechanics, and the cost
accounting — not an arm difference. The pre-registered path to a decisive
test is higher contention density (same-function edits, more tickets per
hot file), longer tickets, and larger N, per §8; a coordination layer can
only show value where the baseline measurably fails.

### 5.3 Replication (run 2, cross-version)

The full suite was re-run the same day. Provenance stamping caught a product
upgrade between runs (nool 6.13.0 → 6.14.0), making run 2 a cross-version
re-test rather than a same-conditions replication — and strengthening the
result: all four Track B bounding findings replicated exactly on 6.14.0
(B5 merge outcomes ≡ git with 15/15 semantic passes; B7 bisect names the
first post-good knot; B3 pluck destroys later unrelated work in both
timeline variants; B4 accepts parseable test-breaking changes). The Track C
grid passed 20/20 (run 1: 19/20; the run 1 interface-mismatch failure did
not recur), with token/turn medians stable within noise per cell and still
no arm separation. The fleet pilot repeated both arms at 8/8 with zero
conflicts; nool's gating overhead was +10 s (run 1) and +3 s (run 2).
Conditions for both runs are indexed in `results/replications/MANIFEST.md`.

Run 3 (next day, nool 6.14.1, CLI 2.1.238) turned the replication suite into
a product-fix verification: three of the four adverse bounds moved, exactly
as the pre-registered re-test contract intends. B5's contended scenarios —
same-anchor and same-file-different-functions — now converge 15/15 clean in
the nool arm via a new MergeReconcile union stage (git remains 1/15 on the
identical branch sets; the disjoint negative control stays 15/15 in both
arms). B3's selective undo now removes the damage 5/5 while preserving later
unrelated work 5/5 in both timeline variants. B7's bisect names the true
culprit. 

The B4 finding was clarified by testing both governance paths: the **default
governed path** (`nool propose --solidify`) **rejects** test-breaking changes
by running project-level tests; the **explicit relaxed path** (`--fast`)
**accepts** them as designed — this is not a validation failure but a
governance-mode semantics test. The benchmark now separates: (1) does the
default governed path reject semantic violations? Yes. (2) Does `--fast`
intentionally permit greater risk? Yes. (3) Can organizations restrict
invocation of the relaxed path? (Track F). The Track C grid scored 18/20 —
singles 5/5 in both arms; one failure in each multi-agent cell (multi_git
r4: an agent left an empty test file that broke the build; multi_nool r2:
an inter-agent interface mismatch, the same failure mode as run 1) — still
no arm separation. Landing latency rose with the fixes: nool medians of
301–507 ms on 6.14.1 versus 120–260 ms in runs 1–2; git's medians also rose
on the same host (39–50 ms versus 17–23 ms), so the environment contributes
to the absolute shift and the robust statement is the ratio, roughly 7–10×
git in every run.

### 5.4 Scale-up 1 — function-level contention (10 agents, 20 tickets)

The pilot's escalation path was pre-registered before any scale data
(design spec, scale-up 1, 2026-08-20): corpus v2 keeps the 8 pilot tickets
and adds 12 whose contention is at function level — cluster A (t9–t11)
modifies the same function body (`service/billing.go` Invoice, the regime
where B5 shows textual merge fails), cluster B (t12–t14) functions in the
same handler file, cluster C (t15–t17) the same store file — at N=10
workers, 2 reps per arm, same pinned model (claude-sonnet-5, nool 6.14.1,
CLI 2.1.238). Prediction: the git arm suffers integration conflicts on
each cluster's 2nd/3rd merges; the nool arm's gated dispatch serializes
clusters so later members branch from integrated state and compose.

| Metric (per rep) | git_fleet r1 | git_fleet r2 | nool_fleet r1 | nool_fleet r2 |
|---|---|---|---|---|
| Tickets accepted | **1/20** | **13/20** | **19/20** | **19/20** |
| Clean merges | 14/20 | 13/20 | 20/20 | 20/20 |
| Final main health | **build broken** | green | green | green |
| Wall time | 100 s | 106 s | 143 s | 179 s |
| Agent spend | $3.80 | $3.87 | $3.68 | $3.90 |
| Spend on failed integrations | $1.40 | $1.57 | $0 | $0 |

The prediction held in both halves, and the git arm failed in two distinct
modes. Mode one, predicted: cluster members conflict at the merge queue —
across the two git reps, cluster A cleanly merged 1/3 and 1/3, cluster B
1/3 and 1/3, cluster C 3/3 then 1/3; every conflict was a 2nd/3rd member
of a cluster (plus t20). Mode two, not predicted but more damaging: in git
rep 1, t17's merge was textually clean yet broke the build, and because
acceptance is scored on final main state, every ticket whose test imports
the poisoned package failed — 13 previously-landed tickets were voided and
only the fully-independent t19 survived, an 18-ticket loss from one
absorbed merge. This is the fleet-scale version of run 1's "clean merge,
broken integration" single observation, and it makes the git arm's outcome
distribution bimodal: either contention losses only (13/20) or
near-total loss (1/20).

The nool arm composed every cluster: 20/20 clean merges in both reps,
main green after every merge, 9/9 cluster tickets accepted in both reps.
The cost is serialization: wall time +40–70% over git (143 s and 179 s vs
100–106 s) at equal agent spend. Cost per accepted change: nool $0.19 and
$0.21 vs git $3.80 and $0.30.

Both nool reps failed the same ticket, t2 — and this is a corpus artifact
worth recording: t2's pilot-era acceptance test hard-codes an invoice
total that assumes base tax semantics, and cluster A's t10 adds a
processing fee to Invoice. The artifact only fires when all of cluster A
lands, i.e. it exclusively penalizes the arm that integrates contended
work successfully; scored as failures per protocol, not rescored. Zero of
the nool arm's non-acceptances are integration failures.

Deviations, all recorded in the run ledger: concurrent `git worktree add`
setup raced under 10 workers and killed one git rep before any outcome was
recorded — spend lost, no data; creation is now serialized in both arms.
The first nool rep ran with a harness dispatch-gate bug — tickets admitted
in the same scheduling batch did not gate each other, so t9 raced t10 and
t12 raced t13 from a shared base and both conflicted (18/20 accepted); it
is kept in the data as a labeled variant, understates the nool arm, and is
excluded from the primary comparison. A prior 10-worker git rep collected
on nool 6.14.0 before the version bump (15/20 accepted, same per-cluster
conflict pattern) is reported as a prior-version observation. One earlier
git rep was lost to operator-machine memory exhaustion before any record
was written; all subsequent runs executed sequentially under a memory
watchdog.

### 5.5 Scale-up 2 — N=25 and N=35 (pre-registered), N=20 (off-ladder)

Scale-up 2 (design spec, pre-registered before any corpus v3 or N>10
data) specifies a concurrency ladder N in {10, 25, 35, 50} on a hardened
corpus v3 (60 tickets: the 20 v2.2 tickets plus 40 new — 20 deepening
eight hot surfaces to up to 5-ticket same-function clusters, 20
independent fillers), 2 reps per arm per point, guarded lowest-N-first
attempts under a free-RAM watchdog (abort at under 8% free on two
consecutive samples). The N=10 anchor has still not been validly
re-measured on corpus v3 with the pinned claude-sonnet-5 arm (only a
broken adapter trial exists at that point — below); N=25 and N=35 have
now completed, reported here.

**N=25 — pre-registered point, complete after two fixes.** The first two
watchdog-guarded attempts aborted within ~9 seconds of starting: free
memory fell from roughly 37% to 0.4% before any agent subprocess produced
output, consistent with `ThreadPoolExecutor(max_workers=25)` launching 25
concurrent Claude Code CLI processes in one burst on the 16 GB operator
machine. Both aborts cost approximately $0 and left no orphaned
processes. A 1.5-second minimum launch interval was then added to the
harness (`agent_ticket()`, applied identically to every arm, so it
changes launch cadence, not the treatment), which measurably softened a
third attempt's burst (minimum free memory improved to 1.9%) but did not
fully clear it, because baseline free memory had independently fallen to
roughly 4-5% over the session from unrelated background application
growth. The operator directed proceeding unguarded rather than freeing
memory first; with the stagger fix in place, all four N=25 runs then
completed without a memory incident.

One `nool_fleet` rep hit a second, unrelated failure mode: partway
through, the operator's Claude account exhausted its rolling usage
window, and every subsequent ticket's agent call received an immediate
rate-limit rejection instead of doing work — 19 of 60 agents affected,
visible as implausibly short wall times (as low as 3.7 s) clustered
together, driving accepted tickets to 44/60 with zero merge conflicts.
This is an account-quota artifact, not a measurement of either arm; the
raw record is preserved verbatim and excluded from analysis
(`results/trackc/invalidated_2026-08-21_rate-limit-midrun/`), and the rep
was rerun cleanly once the window reset. The results below are the four
clean runs (git_fleet rep 1-2, nool_fleet rep 1, and the nool_fleet rep 2
rerun):

| Metric (per rep) | git_fleet r1 | git_fleet r2 | nool_fleet r1 | nool_fleet r2 |
|---|---|---|---|---|
| Tickets accepted | 41/60 | 40/60 | **60/60** | **60/60** |
| Merge conflicts | 20/60 | 21/60 | 0/60 | 0/60 |
| Final main health | green | green | green | green |
| Wall time | 257 s | 132 s | 326 s | 308 s |
| Agent spend | $10.61 | $9.74 | $10.17 | $6.94 |

Same pattern as scale-up 1 and the N=20 point below: every git_fleet
failure is exactly a merge conflict on a contended-cluster ticket (the
extra conflict beyond the failure count in both reps is t21, the same
neighbor-tolerance corpus artifact noted at N=20); nool_fleet composed
all 60 tickets with zero conflicts in both reps. Cost per accepted
ticket: nool approximately $0.17 and $0.12 versus git approximately
$0.26 and $0.24. This is the first concurrency point above scale-up 1's
N=10 anchor to complete end to end under the pre-registered protocol.

**N=35 — pre-registered point, two build-poisoning events.** Same corpus
v3, claude-sonnet-5, launch-staggered, run unguarded (no watchdog) at the
operator's direction; all four runs completed without a memory or
rate-limit incident.

| Metric (per rep) | git_fleet r1 | git_fleet r2 | nool_fleet r1 | nool_fleet r2 |
|---|---|---|---|---|
| Tickets accepted | 37/60 | **20/60** | **60/60** | **60/60** |
| Merge conflicts | 20/60 | 22/60 | 0/60 | 0/60 |
| Final main health | build ok, tests fail | **build broken** | green | green |
| Wall time | 141 s | 126 s | 312 s | 349 s |
| Agent spend | $6.83 | $6.78 | $6.81 | $6.94 |

Both git_fleet reps show a failure mode beyond plain merge conflicts, at
increasing severity. Rep 1: 20 of 37 failures are merge conflicts on
contended-cluster tickets; 3 more (t54, t55, t58 — independent,
single-file filler tickets with clean merges) fail because the final
main branch builds but `go test ./...` does not pass, consistent with a
package-level symbol collision between disjoint files that git's textual
merge cannot see. Rep 2 is more severe: 22 conflicts, plus 18 further
failures spread across unrelated early tickets (t1-t9, t14-t15, t17-t18,
t30, t32, t38, t49-t50) because the final main branch does not even
build; since acceptance is scored on final main state, every ticket whose
package the poisoning reaches fails regardless of its own merge outcome.
This is scale-up 1's "mode two" (§5.4) — a textually-clean merge silently
breaking the build — replicated at more than 3x scale-up 1's N and a 3x
larger corpus, now observed in both reps rather than one of two, at
increasing severity with N. nool_fleet again composed every ticket with
zero conflicts in both reps; cost per accepted ticket: nool approximately
$0.11 in both reps versus git approximately $0.18 (rep 1) and $0.34
(rep 2, reflecting the poisoning's near-total loss).

**N=20 — off-ladder exploratory point.** Not part of the pre-registered
ladder; collected without the watchdog, between the initial N=25
censoring and the stagger fix, to get a data point at higher concurrency
than the scale-up 1 anchor. Same corpus v3, claude-sonnet-5, 2 reps
per arm:

| Metric (per rep) | git_fleet r1 | git_fleet r2 | nool_fleet r1 | nool_fleet r2 |
|---|---|---|---|---|
| Tickets accepted | 39/60 | 40/60 | **60/60** | **60/60** |
| Merge conflicts | 21/60 | 20/60 | 0/60 | 0/60 |
| Final main health | green | green | green | green |
| Wall time | 135 s | 115 s | 313 s | 304 s |
| Agent spend | $10.31 | $10.35 | $10.40 | $10.21 |

Every git_fleet failure is exactly a merge conflict, and every conflict
lands on a ticket in one of corpus v3's contended clusters (billing,
api/router, store, users, orders, ids, model, api-endpoints); final main
health stayed green both reps because the harness aborts a conflicted
merge rather than leaving the tree dirty, unlike scale-up 1 rep 1's
clean-merge build-poisoning. nool_fleet composed every contended cluster
with zero conflicts, replicating scale-up 1's pattern at twice the
corpus size and twice the worker count. Wall time cost grew steeper than
scale-up 1's N=10 point (nool roughly 2.3-2.7x git's wall time here,
versus +40-70% at N=10) — expected, since corpus v3's denser clusters
serialize more work under gated dispatch; run cost stayed flat (roughly
$10.2-10.4) across arms, so cost per *accepted* ticket separates sharply
(nool approximately $0.17 versus git approximately $0.26 per accepted
ticket).

**Antigravity adapter trial (not a comparison arm).** A new adapter
(`harness/adapters/antigravity.py`) driving Google's `agy` CLI was
trialled at N=10/corpus v3 alongside this work. Both its runs are
recorded as raw data but excluded from every comparison above:
`git_fleet_antigravity` accepted 11/60, `nool_fleet_antigravity` accepted
2/60 with the final build broken — indicative of an unfinished adapter
integration (agy 1.1.x does not yet support the tool-restriction flags
the isolation contract requires), not a treatment effect.

## 6. Evidence map: claims versus current evidence

| Claim | Status | Basis |
|---|---|---|
| C1 correctness | **Untested at power** | Track C shows parity at N=5 on one task; Track D pilot adds contention |
| C2 non-interference | **Positive on 6.14.1, strengthens with N** | scale-up 1: footprint-gated dispatch yields 0 integration failures vs git's 6–7 conflicts plus one build-poisoning per two reps; B5 run 3: contended merges converge 15/15 on 6.14.1 (were ≡ git, 1/15, on ≤6.14.0); N=25 (§5.5, pre-registered): nool 0/60 merge conflicts both reps vs git 20/60 and 21/60; N=35 (§5.5, pre-registered): nool 0/60 both reps vs git 20/60 and 22/60, with git's rep 2 additionally build-poisoned; N=20 off-ladder: nool 0/60 both reps vs git ~21/60 and ~20/60 |
| C3 decision survival | **Untested** | Track E designed; D2 handoff designed |
| C4 safe concurrency | **Holds through N=35; N=10/v3 anchor and N=50 open** | B2 to N=15 scripted; scale-up 1 at N=10 (corpus v2): nool acceptance 19/20 both reps while git degrades to 13/20 and 1/20; N=25 (§5.5, pre-registered, corpus v3): nool 60/60 both reps vs git 41/60 and 40/60; N=35 (§5.5, pre-registered, corpus v3): nool 60/60 both reps vs git 37/60 and 20/60, with git's severity increasing (a full build-poisoning event in rep 2) — direction consistent with C4 strengthening, not merely holding, as N grows, though the N=10/v3 anchor itself is not yet validly measured with claude-sonnet-5, so this is not yet a same-corpus curve anchored at N=10; N=20 off-ladder: nool 60/60 both reps vs git 39/60 and 40/60; N=50 unattempted |
| C5 cost per accepted change | **First separation, one scale point** | scale-up 1: $0.19–0.21 (nool) vs $0.30–3.80 (git) per accepted change at equal per-run spend; wall +40–70% |
| P3 deterministic governance | **Governed path: positive; Relaxed path: explicit opt-in** | B4 (both paths); Track F tests configured enforcement incl. authority controls & raw-git bypass |

The honest present-tense summary: on 6.14.1, nool's measured advantages are attribution integrity under concurrency, token-economical context retrieval, fleet non-interference through footprint-gated dispatch (scale-up 1), and — new in run 3 — convergent merges, descendant-preserving selective undo, and correct bisect localization, three bounds that moved because the product did. The default governed path provides **semantic commit gating** (B4: test-breaking changes rejected at propose); the `--fast` relaxed path is an explicit, attributable operator opt-in for rapid iteration with deferred validation. The remaining measured gaps are per-operation latency (roughly 7–10× git across all runs) and the authority/control question for the relaxed path (Track F). Goalposts are fixed by pre-registration; the bounds moved only when the product did, which is the property the suite was built to have.

## 7. Threats to validity

**Vendor-run.** Author is affiliated with Nool, Inc. Mitigations: pre-registration before data; negative controls that behaved as predicted (B5 disjoint 15/15 both arms); publication of raw data and negative findings — three of which are adverse to the vendor's headline claims; conclusion-free analysis code. Independent replication remains the only complete mitigation and requires the no-cost evaluation license identified in the replication package.
**Corpus integrity.** A same-day incident (§3) landed partial ticket solutions directly against the benchmark's live source template between the scale-up 2 pre-registration and data collection; detected before any scale-up 2 run via a diff against the pre-registration commit, and fixed before the N=20/N=25 data in §5.5 was collected. All Track D results in this report were verified collected under a corpus matching its pre-registration commit exactly; diffing `starter/` against that commit is now part of the pre-run checklist rather than a one-time fix. Separately, one N=25 `nool_fleet` repetition was corrupted mid-run by the operator's Claude account hitting its usage limit (§5.5); the raw record is preserved but excluded from every analysis and figure in this report, and the repetition was rerun cleanly rather than folded into an average.
**Construct validity.** Track C/D tasks are small and synthetic (disclosed); enterprise-scale codebases and horizons are the object of the roadmap, not this phase. B2's shared-workspace design measures a regime git does not recommend (its idiom is worktrees); we report it as the coordination-substrate stress test it is, alongside the worktree-based Tracks C/D.
**Statistical power.** N=5 LLM cells detect only large effects; all such comparisons are labeled. Deterministic benchmarks carry mechanism claims at high repetition instead.
**Single model/harness.** One pinned model on one harness; the adapter contract (with mandatory environment isolation) defines the replication path for gemini/codex/pi.
**LLM nondeterminism.** Replication reproduces the protocol and effect directions, not exact values; every run carries its own provenance.

## 8. Roadmap and power analysis for the decisive proofs

**P1 — Fleet correctness at scale.** Scale Track D: N ∈ {5, 25, 50} workers, 50–200 tickets over a vendored ~50 kLOC service, overlap ratio as a controlled factor, ≥3 reps per point. Estimated LLM cost at observed per-ticket spend (~$0.2): $200–800 per concurrency point per arm. Decision rule (pre-registered before scale-up): C4 supported if nool's acceptance rate at N=50 is within CI of its N=5 rate while git's declines. First point collected (§5.4): at N=10 with function-level contention, nool holds 19/20 while git falls to 13/20 and 1/20 — direction consistent with C4. The hardened corpus (v3: t2 fixed, 60 tickets, denser hot-surface clusters) and the scale-up 2 ladder (N in {10, 25, 35, 50}) were pre-registered next; N=25 initially proved infrastructure-censored on the operator's 16 GB machine, resolved by a launch-cadence stagger fix in the harness. N=25 and N=35 have now completed (§5.5): at N=25, nool 60/60 both reps vs git 41/60 and 40/60; at N=35, nool 60/60 both reps vs git 37/60 and 20/60, with git's rep 2 a full build-poisoning event — the separation strengthens, not merely holds, as N climbs. An off-ladder N=20 point, collected while N=25 was still blocked, shows the same pattern. Remaining before the ladder is complete: a valid claude-sonnet-5 N=10/v3 anchor (corpus v3's N=10 point has only been exercised by a broken adapter trial so far), and the N=50 point.
**P2 — Longitudinal memory (Track E).** 100+ sequential tasks with scheduled decision injections; slope comparison on correctness and constraint adherence. SlopCodeBench adaptation runs alongside as the published-instrument anchor. Est. $150–400 per arm per rep.
**P3 — Deterministic governance (Track F).** Governance configured via nool's own scaffolding; prohibited-change battery where violation is the easiest route; adversarial conditions include fresh sessions and the raw-git bypass. Mostly deterministic scoring; LLM cost bounded (~$50 per battery). B4 predicts default-config gaps; the benchmark quantifies enforcement before and after configuration and product fixes.

## 9. Conclusion

A coordination layer for agent fleets must be judged on final-system outcomes under contention, scale, and time. We built and pre-registered the instruments to do so, and Phase 1 delivers a candid baseline: real, measurable advantages in exactly the places an audit-minded enterprise would look (attribution, context economy, commit gating), and equally measurable gaps in the places the coordination pitch leads with (merge, selective undo, regression localization, semantic enforcement). The suite's value is that it will render the same verdict, at the same goalposts, when the product closes those gaps — which is what makes the eventual positive result, if it comes, worth believing.

## Data and code availability

All benchmarks, raw results, transcripts index, pre-registration history, and this report: `github.com/noolinc/nool_long_eval_bench` (Apache-2.0, NOTICE attribution to Nool, Inc.). Deterministic Track B replicates with Docker + the nool CLI alone; LLM tracks require an Anthropic-authenticated Claude Code CLI and a nool evaluation license.

## References

CooperBench — github.com/cooperbench/CooperBench. SlopCodeBench — arXiv:2603.24755. SWE-EVO — arXiv:2512.18470. RoadmapBench — arXiv:2605.15846. Co-Coder — arXiv:2606.00953. The Specification Gap — arXiv:2603.24284.
