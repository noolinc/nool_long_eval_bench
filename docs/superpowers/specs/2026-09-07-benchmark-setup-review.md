# Benchmark setup review: does the suite answer the enterprise question?

**Date:** 2026-09-07
**Status:** Review, with one new analysis module and a costed improvement plan.
**Question under review:** Is nool economically viable for enterprises running
long-horizon projects, or are existing agents and harnesses enough?

This review reads the design spec (sections 1 to 8i), the frozen v4 protocol,
the paper's evidence map and threats section, the inference code, the cost
model, the corpus builder, and the full run ledger (154 fleet records) as of
the 1.0.0 checkpoint. It is written so that every claim below can be checked
against a file in this repository.

## 1. Verdict

The suite is unusually honest: pre-registered, negative results published,
incidents quarantined verbatim, analysis code that emits numbers and no prose.
That discipline is the suite's main asset and should not be traded away.

But the question it answers is not the question above. The question has four
load-bearing terms: *long-horizon*, *economically viable*, *enterprise*, and
*existing harnesses*. The suite has an instrument for none of them. What it
measures, rigorously, is the conflict rate during a 5 to 13 minute concurrency
burst on a 304-line Go service against control schedulers written by the
suite's own author. That is a real result about coordination *policy*. It is
not yet a result about whether an enterprise should pay for nool.

Section 4 below adds the one missing piece that can be built from data already
collected: a cost-effectiveness layer. Its output reframes the whole question
around a single parameter, footprint accuracy, and that reframing is the most
useful thing this review has to say.

## 2. Construct validity: the question is not being asked

**2.1 No long-horizon instrument exists.** Every fleet run starts from the
pinned starter and ends within minutes. H5 (longevity) has zero data. Track E,
the paper's own "P2 decisive proof", is designed and not built. SlopCodeBench
(A2) is not built. The related-work section cites exactly the right instruments
(SWE-EVO, SlopCodeBench erosion slopes) and then never uses them. A reader who
sees "long-horizon" in the title finds an afternoon.

**2.2 The comparator is wrong for the question.** "Existing agents and
harnesses are enough" is a claim about products that exist: Claude Code's
native worktree subagents, a GitHub merge queue, plain CI. None is an arm.
Every git arm is a control the author wrote. And the suite has already
produced the "existing harness is enough" result without naming it: 8g showed
a wave scheduler of roughly fifty lines plus plain `git merge` matching nool
exactly (59.7 vs 59.3 accepted, zero conflicts, n=3), and the 5.6 audit found
`nool_fleet`'s dispatch was harness-computed with nool's verdicts never
consulted. After those two findings, the only product-attributed separation in
154 runs is the 8d noise dose-response, roughly fifteen runs at n=2 to 5.

**2.3 There was no economic model.** `cost_usd` is the Claude CLI's own
`total_cost_usd`: LLM tokens and nothing else. C5, "cost per accepted change",
was LLM dollars per ticket. That omits every cost the enterprise argument rests
on: engineer time to redo a failed ticket, team time lost to a broken main
branch, the priced value of nool's measured +50 to 100 percent wall time, and
nool's own fee. Section 4 fixes this over existing data.

**2.4 Scale.** The starter corpus is 304 lines of Go. The paper's threats
section discloses "small and synthetic", which is honest; the roadmap's vendored
~50 kLOC service has not materialised. No enterprise-codebase claim survives a
304-line corpus.

## 3. Verifiability: the suite violates its own frozen protocol

`protocols/fleet_v4.json` is status `frozen`, sha-pinned, cited in every
record. Its requirements against what was collected:

| protocol v4 requires | collected |
|---|---|
| at least 10 reps per arm-cell | 2 to 5; `MIN_REPS_FOR_INFERENCE = 5` in `summarize.py` contradicts the protocol's 10 |
| four languages: go, typescript, python, java or rust | go only |
| ticket tiers `prescriptive` and `ambiguous` | `all` only; eight ambiguous tickets are tagged in `build_v3.py` and never analysed separately |
| noise levels 0 / 0.1 / 0.25 | 0.1 / 0.3 / 0.5 |
| cross-repository | one synthetic repository |

A reviewer who opens the protocol file finds every row. Either meet the
protocol or freeze a v5 that describes what was actually done.

**Version churn.** nool-arm evidence spans six product versions, 6.14.0 to
7.2.0. Three product defects were found and fixed mid-study; bounds "moved
because the product did". That is honest and it is also fatal to a single
coherent claim, because every headline number lives on a different binary. The
installed 7.2.0 binary additionally reports its git sha as dirty.

**Amendment frequency.** 8g was amended twice within hours of being written;
8h and 8i were added the same day. Every amendment was legitimately pre-data.
A reviewer still counts amendments, and this spec has many.

**Audit trail gaps.**
- Transcripts are not archived. `.gitignore` excludes `results/**/transcripts/`:
  0 of 9,798 are committed. The spec promises "full transcript archived"; the
  paper promises a "transcripts index". The index exists; the evidence does not.
- Model pinning is porous. Observed 2026-09-06: the same `claude-sonnet-5` id,
  five days apart, moved both arms by exactly minus five tickets on identical
  inputs, then plus one on the next rep. The id pins nothing about
  provider-side behaviour. Same-batch pairing is the only defence and must be a
  stated rule, not a habit.
- Single model. Only sonnet-5 carries evidence weight. 8f (Fable) is
  pre-registered and has never run. Opencode's 28 runs score 0 to 2 of 60,
  which is a broken adapter, not a data point.
- LLM tracks are not containerised. Docker covers Track B only.
- No independent replication, ever. The paper says this is the only complete
  mitigation for the vendor-run threat. It is correct.

## 4. The cost-effectiveness layer (new, `analysis/cost_effectiveness.py`)

Every fleet record already carries LLM spend, accepted and failed ticket
counts, merge conflicts, main-branch poisonings, and wall time. The module
prices them:

    total = llm + fee + failed * C_rework + poisonings * C_poison
          + wall_hours * C_hour
    per_accepted = total / accepted

and, because the decisive unknown is C_rework (what one failed ticket costs
the organisation to redo), it reports the break-even C* per matched cell at
which the nool arm's cost per accepted ticket equals the git arm's, rather than
assuming a value. Conflicts are shown but not priced by default, to avoid
double-counting a failed ticket that already carries C_rework. The module
emits numbers only.

*Data note on `poisonings`.* The module reads `evolution.broken_main_merges`,
which counts merges after which main's build or smoke health was red, whether
or not it later recovered. That is the right quantity for C_poison (each event
is a window in which a real team is blocked) but it is not the ticket-voiding
cascade of paper 5.4. The two can diverge sharply: `git_scheduled` run
`976968d7` (v3.1, N20, zero noise) accepted 60 of 60 tickets while recording
16 red-health merges and finishing with smoke red. Per-ticket acceptance and
main-branch health are independent instruments and the suite scores both;
readers pricing C_poison should know which one they are paying for.

**4.1 Base case** (C_poison = C_hour = fee = 0; only C_rework unknown), sonnet-5,
cells with at least 2 reps per arm:

| pair | cell | acc g / n | failed g / n | llm$ per acc g / n | C* |
|---|---|---|---|---|---|
| git_scheduled vs nool_gated | v3 N10, zero noise | 60.0 / 60.0 | 0 / 0 | 0.115 / 0.116 | nool never cheaper |
| git_scheduled vs nool_gated | v3 N35, zero noise | 60.0 / 59.8 | 0 / 0.2 | 0.118 / 0.117 | nool never cheaper |
| git_scheduled vs nool_gated | v3.1 N20, d0.1/a0.1 | 56.8 / 58.0 | 3.2 / 2.0 | 0.154 / 0.149 | nool always cheaper |
| git_scheduled vs nool_gated | v3.1 N20, d0.5/a0.5 | 49.0 / 53.0 | 11.0 / 7.0 | 0.179 / 0.164 | nool always cheaper |
| git_scheduled vs nool_gated | v3.1 N45, d0.5/a0.5 | 48.2 / 55.0 | 11.8 / 5.0 | 0.169 / 0.131 | nool always cheaper |
| git_planned vs nool_planned | v3.1 N35, zero noise | 59.7 / 59.3 | 0.3 / 0.7 | 0.113 / 0.107 | nool never cheaper |
| git_fleet vs nool_fleet | v3 N35, zero noise | 28.5 / 59.8 | 31.5 / 0.2 | 0.239 / 0.131 | nool always cheaper |

Per-accepted cost at C_rework = 100 USD, the same cells, git then nool:
v3 N35 zero noise 0.12 vs 0.45; v3.1 N20 d0.1 5.79 vs 3.60; v3.1 N20 d0.5
22.63 vs 13.37; v3.1 N45 d0.5 24.52 vs 9.22; planned pair 0.67 vs 1.23;
git_fleet pair v3 N35 110.77 vs 0.47.

**4.2 Sensitivity** (C_hour = 100 USD per fleet-hour, fee = 5 USD per run to
nool), same cells: the zero-noise verdicts do not move; every noise cell
acquires a finite break-even between 1 and 4 USD per failed ticket at N20 to
N40, 39 USD at v3.1 N35 zero noise, and stays "always cheaper" at N45 heavy
noise. The unscheduled `git_fleet` pair breaks even at 0 USD in every cell
with failures.

**4.3 What the numbers say, stated as numbers.** With accurate (oracle)
footprints there is nothing for nool to buy back: both scheduled arms accept
everything, nool costs marginally more in tokens and time, and no rework price
makes it cheaper. The planned-arm pair is the same result from the other side:
a free scheduler dominates. Under footprint noise the picture inverts, and a
failed ticket has to be worth only single-digit dollars for nool to win even
when its extra wall time and a per-run fee are priced. Against an unscheduled
git fleet nool wins at any positive rework cost, which is the policy result 5.6
already attributed to scheduling rather than to the product.

The economic question therefore reduces to one parameter the suite has never
measured in the field: **how accurate are the footprints a real fleet
actually has?** With an oracle, existing harnesses plus a scheduler are enough.
Without one, nool pays for itself at any realistic rework cost. Neither the
oracle nor the noise model is a measurement of real fleets; 8e's observation
that "a production fleet has no oracle to perturb in the first place" is the
most important open item in the suite.

## 5. Improvement plan, in order

**A. Cost-effectiveness layer.** Done, section 4. Add to the paper as the C5
result and retire LLM-dollars-per-ticket as the headline.

**B. Real comparator arms, roughly 30 USD.** `claude_native`: Claude Code's
own subagent and worktree mode with no harness scheduler and plain merge.
`git_mergequeue` is already approximately `git_gated_queue`. If `claude_native`
matches nool at N35, "existing harnesses are enough" is established at this
scale and the paper should say so.

**C. Agent-discovered footprints.** The single most decision-relevant
measurement: replace the oracle with footprints each agent declares itself
after reading the ticket, record the declared-versus-actual error rate, and run
the scheduled pair on those. This converts the noise axis from a simulation
parameter into a measurement of what real fleets have. Roughly 20 runs.

**D. Track E.** The only instrument that measures long horizon. One hundred
sequential tasks on one repository, decisions injected at scheduled points,
slope of correctness and constraint adherence over task index. Designed; build
it. The paper's own estimate is 150 to 400 USD per arm per rep.

**E. One real repository.** A 10 to 50 kLOC open-source Go service with tickets
derived from real issues. Protocol v4 calls itself cross-repository; make it so.

**F. Frozen-version confirmatory batch.** One nool build with a clean sha and a
published hash, one recorded model date, ten reps on three cells:
`git_competitive` vs `nool_gated` at zero and very-heavy noise, plus
`claude_native`. Everything collected so far becomes exploratory; this batch
becomes the claim.

**G. Archive and replicate.** Transcripts to LFS or Zenodo with per-file hashes
in the manifest. One external replicator on Track B plus one LLM cell. Until
this happens the vendor-run threat is unmitigated by the paper's own account.

The through-line: the suite has already, honestly, produced most of the
evidence that a scheduler is the active ingredient under accurate footprints.
The economic question is whether nool is worth more than that scheduler when
footprints are what real fleets can actually produce, and that is the one
measurement not yet made.
