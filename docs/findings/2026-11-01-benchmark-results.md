# Benchmark results through 2026-11-01

This page is a guide to the results in this repository. The tracks measure
different things, so there is no combined Nool-versus-git score. I have kept
small pilots, repeated mechanism tests and fleet runs separate below. Raw data
and the older, fuller reports remain the source for each number.

## What the evidence says

The most repeatable results are the deterministic Track B mechanism checks.
On Nool 7.19.0, Nool's B1–B9 outcomes matched the 7.8.0 rerun. Git's swept
commit counts in B2 varied under contention, and timings shifted in both arms.
That does not mean Nool is free: landing changes was slower than a hooked Git
baseline, with the gap increasing on larger changes. The synthetic B10 probe
also found that admission cost grows with repository size, though much more
slowly than the repository itself.

The fleet study gives a narrower answer than “Nool beats Git.” When ticket
footprints are accurate, a Git scheduler using the same declared footprints
matches the Nool arms. With deliberately noisy footprints, Nool accepted more
tickets in the measured runs. That result is promising, but the noise cells
have two repetitions and the dispatch gate is implemented in the harness; it
is not yet strong evidence that the product itself caused the difference.

Coding-agent results are still early. The earlier Claude Track C grid showed
no separation between Git and Nool. A new Codex run passed all four cells on
one Go task, but one run per cell cannot establish a difference. The raw
transcripts contain token counts; the JSONL records do not, because the
adapter's event parser was fixed after this run. The CLI did not provide a
monetary cost for these sessions.

The enterprise probes show that several local controls work, and one audit
check does not. The smoke run passed 35 of 36 checks; imported-history
integrity failed and remains visible in the artifact. The separate 50-client
lease probe passed its three checks. Neither probe is a production
qualification or a complete buy-versus-build comparison.

## Results by track

| Track | Latest result | What it supports | Main limit |
|---|---|---|---|
| B1–B9, mechanism tests | Nool 7.19.0 rerun; Nool mechanism outcomes matched 7.8.0, while Git sweep counts varied | Stable outcomes for concurrent edits, recovery, guardrails, merging, retrieval, localization and blast-radius checks | Synthetic repositories and scripted operations; measured latency varies by machine and is material for large changes |
| B10, admission cost | Synthetic scale probe at R=100, 1,000 and 10,000; separate replay of 40 real change records | Admission rose about 3.5–9.7× over a 100× increase in synthetic repository size, depending on change surface. The real-history replay had 39 landed and one refused record | The largest synthetic tier has one run; synthetic Go shape and one real repository do not establish performance on buyer code |
| B11, agent bus | Harness source exists; no committed result artifact yet | No result claim | Run and record it before treating it as evidence |
| C, coding-agent grid | Claude: three five-repetition grids, 19/20, 20/20 and 18/20 accepted; Codex: 4/4 cells passed once | The task can be solved in both VCS conditions; the Claude runs did not separate the arms | Small synthetic task, one-repetition Codex pilot, and no cost data for Codex; no procurement conclusion |
| D, fleet coordination | Runs through N=35 plus a footprint-noise comparison | Scheduled Git matches Nool with accurate footprints; under injected noise Nool retained a small acceptance lead in the two-run cells | Most cells are below the preregistered replication target; dispatch attribution and final-main health need care |
| G, brownfield pilot | Nine raw ledger entries across five conditions | Static architecture violations persisted across prompt and handoff conditions; the unknown-email edge case varied across runs | One repository, one model, changing pilot conditions and few runs; not a comparative product evaluation |
| Enterprise probes | Smoke: 35/36 checks; 50-client lease probe: 3/3 | Local scale/context, evidence, approval and lease mechanisms can be exercised; the smoke audit failure reproduces | Single-machine generated fixtures, no hosted controls, and no real enterprise workload |

The planned external benchmark adaptations (Track A) have no collected
results. B11 and the Track D N=50 agent-fleet point are also outstanding.

## Track B

The 7.19.0 rerun compared with 7.8.0 found Nool's B1–B9 mechanism outcomes
unchanged. Git's swept-commit counts varied under contention. The more useful
results are mixed:

- B2 recorded all Nool edits at N=2, 5 and 15 without lost edits or retries;
  Git sometimes swept one writer's change into another commit.
- B3 removed the bad landing and preserved unrelated later work in all five
  repetitions on both Nool timelines.
- B4's governed Nool path rejected test-breaking changes; Git and Nool fast
  mode accepted them in the fixture. A passing syntax check is not a test gate.
- B5 merged all 15 branches in each Nool topology. Git merged all disjoint
  branches but only one of 15 in each contended topology.
- B6 retrieved the expected file and symbol context. The combined search and
  materialization used 620 bytes, close to the 658-byte grep-and-read control.
- B7 localized the regression in 1,793 ms with Nool and 2,668 ms with Git
  bisect on this fixture.
- B8 measured precision 1.0, recall 1.0 and false-positive rate 0 across its
  tested topologies. B9 measured mean recall 1.0 and false-positive rate 0
  across 24 code languages; the six non-code formats had no recall target.

Those results sit beside a real cost. On 7.19.0, fast Nool landing took about
6.5×, 9.8× and 39× as long as hooked Git for 1-, 10- and 100-file changes.
Full-mode ratios were about 10×, 14× and 54× against a Git hook that ran
`go vet`. Absolute times were milliseconds to roughly two seconds in these
fixtures, not a prediction for a production checkout.

B10's synthetic data does not support the earlier “flat admission cost”
hypothesis: admission rose as R grew. Across the measured change surfaces, it
grew about 3.5–9.7× while R grew 100×. Evidence work grew faster. The separate
real-history replay covered 40 records in one Nool repository; its 1.34 s
median includes cold local processing and should not be read as a warm-server
latency. B10's full interpretation and exclusions are in the [B10 report](2026-09-16-b10-admission-cost.md)
and [7.19.0 rerun](2026-10-12-trackb-7.19.0-rerun.md).

B11 has code but no result file under `results/micro/`. It is not included in
the evidence above.

The v3.1 leave-one-out, mutation and negative-corpus JSON files under
`results/micro/` check whether the fleet tasks behave as intended. They are
corpus-quality validations, not measurements of a Nool-versus-Git effect.

## Track C: coding-agent runs

The historical Claude grid used five repetitions per cell on `redux_go`. The
three recorded grid totals were 19/20, 20/20 and 18/20 accepted; the report
found no reliable arm separation. The November Codex run is a separate pilot,
not another replication of those Claude results.

| Cell | Build | Hidden tests | Agent time | Input tokens (cached) | Output tokens | Completed tool items |
|---|---:|---:|---:|---:|---:|---:|
| `single_git` | pass | pass | 37.6 s | 106,599 (97,408) | 3,964 | 5 |
| `single_nool` | pass | pass | 43.9 s | 132,722 (120,704) | 5,230 | 5 |
| `multi_git` | pass | pass | 36.5 s + 40.7 s | 214,669 (194,560) | 6,672 | 13 |
| `multi_nool` | pass | pass | 44.1 s + 64.4 s | 440,172 (406,144) | 11,272 | 22 |

The multi-agent times are per worker, not cell wall-clock time. Input and tool
counts above were read from the raw Codex transcripts. The run records have
nulls for these fields because the adapter originally expected wrapped JSONL
events; Codex emitted them at the event's top level. That parser is now fixed.
Cost is still null because Codex did not emit a monetary amount. An earlier
four-cell attempt used an exported API key instead of the active ChatGPT login
and failed for lack of API credits; its failed scores are in `runs.jsonl` but
are excluded from this table.

The CLI exposed `gpt-5.6-luna`; it did not expose `gpt-6-luna`. The successful
run therefore used the exact supported slug, with the same model requested in
all cells. Its run IDs are `redux_go_single_git_r0_27226812`,
`redux_go_single_nool_r0_5ffe1cda`, `redux_go_multi_git_r0_fe238203` and
`redux_go_multi_nool_r0_e21926f2`.

## Track D: fleet coordination

The fleet results cover several corpora and harnesses, so do not pool their
ticket counts into one rate. On the 60-ticket v3.1 noise comparison at N=20,
both arms averaged 60/60 with accurate footprints. With injected footprint
noise, Nool averaged 58/60 under light and heavy noise and 53/60 under
very-heavy noise; scheduled Git averaged 56/60, 55/60 and 49/60.
The heavy-noise 58/60 versus 55/60 result repeated twice. Other cells have
one or two runs, below the suite's replication goal.

There are two important qualifications. The harness, not Nool, made the
dispatch hold/admit decision; Nool's announce/conflict output was recorded
but did not control dispatch. Also, accepted-ticket count can disagree with
the health of the final main branch: one zero-noise Git run accepted every
ticket but ended with a broken main branch. The [fleet findings report](2026-08-21-findings.md)
and [suite design](../superpowers/specs/2026-08-20-nool-benchmark-suite-design.md)
describe the arms, quarantined runs and remaining replication work. N=50 is
not complete.

## Track G: brownfield pilot

The gift-shop pilot tested architecture conformance, prompt size and session
handoff in one Go service. The raw ledger has nine rows, not just the five
initial conditions in the original report. `git_thin` passed all four
behavioral tests in both entries. `nool_thin` and both handoff conditions
passed three of four; the failure was graceful handling of an unknown email.
The four `git_fat` entries include three 4/4 outcomes and one 3/4 outcome.
Static layering and money-arithmetic violations persisted across the runs.

This pilot is useful for identifying failure cases, not for deciding between
products. The conditions were exploratory, the raw ledger has repeats, and
the report's original table describes the initial five-condition pass. See
the [pilot writeup](2026-08-23-trackg-brownfield-pilot.md) before using any
one cell as a headline number.

## Enterprise mechanism probes

The 2026-11-01 smoke profile ran four local scenarios. Scale/context passed
10/10 checks, approval passed 8/8, and four-client lease coordination passed
3/3. Governance passed 15/16: imported-history integrity failed with
`parent_missing`, reproduced in both the source repository and a fresh
clone. That failure remains in
[`2026-11-01-smoke.json`](../../results/enterprise/2026-11-01-smoke.json).

The separate 50-client lease artifact passed all three coordination checks.
It does not run the 110K-line scale fixture. Neither artifact tests hosted
branch protection, identity-provider integration, residency, or operation
over a working day. The full scope and procurement gaps are listed in
[`enterprise-benchmarks.md`](../enterprise-benchmarks.md).

## Results index

- [Track B 7.19.0 rerun](2026-10-12-trackb-7.19.0-rerun.md), [B10 scaling](2026-09-16-b10-admission-cost.md),
  [per-version replication manifest](../../results/replications/MANIFEST.md)
- [Fleet findings](2026-08-21-findings.md), [paper and methods](../paper/2026-08-nool-fleet-study.md)
- [Track G brownfield pilot](2026-08-23-trackg-brownfield-pilot.md)
- [Enterprise benchmark scope](../enterprise-benchmarks.md)
- Track A external adaptations are planned; no results have been collected.
- Raw files: [`results/micro/`](../../results/micro/), [`results/trackc/runs.jsonl`](../../results/trackc/runs.jsonl),
  [`results/trackc/fleet_runs.jsonl`](../../results/trackc/fleet_runs.jsonl),
  [`results/trackg/runs.jsonl`](../../results/trackg/runs.jsonl),
  [`results/enterprise/`](../../results/enterprise/)
