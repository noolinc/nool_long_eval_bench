# B10 status: admission cost vs repository size and change surface

**Status:** two of three planned parts built and run, including the full R ∈ {100, 1,000,
10,000} scaling sweep · 2026-09-16
**Pre-registration:** the admission-control research session's plan (`docs/superpowers/plans/` on the Nool product repo, 2026-09-15, "incremental admission control"), which specified `b10_self`, `b10_asymptotic`, and `b10_oss`, the pre-registered pass rule (`flat_in_R := ratio_10k_over_100 <= 2.0`), and the fixture design this doc implements.
**Scripts:** `micro/b10_self.py`, `micro/b10_fixture.py`, `micro/b10_assurance_scaling.py`. Results: `results/micro/b10_self.json`, `results/micro/b10_assurance_scaling.json`.

## What B10 tests

The Nool product's propose-time gate computes a "blast envelope" (which files/symbols a
change reaches), an "affected contracts" set (assertions, invariants, obligations, sensitive
paths it threatens), and a deterministic "evidence plan" (how much evidence — precheck,
selected tests, package tests, human approval — the change needs). The question: does
**admission** work (computing the envelope + deciding the plan) cost roughly the same
regardless of how large the surrounding repository is, while **evidence** work (compiling,
running tests) genuinely grows with repository size? If so, Nool's cost is priced by the
change, not the codebase, for the part of the pipeline it can actually control.

## Summary of findings so far

**F1 — The deterministic evidence-plan decision itself is free.** Across every measured
propose call in both parts (60+ real and synthetic admission calls), `evidence_plan`'s own
resolution time (`plan_ms`) was 0ms. The plan is a pure function over already-computed
inputs; it adds no measurable cost of its own. This was true regardless of repository size or
change surface.

**F2 — Admission cost is sub-linear in repository size across the full 100x range measured,
but the advantage shrinks sharply as the repository grows further; the second decade is
markedly worse than the first.** On the synthetic fixture (`b10_assurance_scaling`,
R = 100 / 1,000 / 10,000 Go packages, three fan-in levels D = {0, 4, 16}, 3 reps each), the
gate-only admission median (D-averaged) grew:

| R | admission median | ratio vs. prior decade | fast_vet median | ratio vs. prior decade |
|---|---|---|---|---|
| 100 | 120.3ms | — | 434.9ms | — |
| 1,000 | 271.6ms | 2.26x | 1,660.9ms | 3.82x |
| 10,000 | 1,809.2ms | 6.66x | 23,063.7ms | 13.89x |

The first decade (100→1,000) missed the pre-registered `<= 2.0x` "flat" bar narrowly
(2.19x–2.30x per D). The second decade (1,000→10,000) misses it badly — **6.3x–7.0x** per
D, roughly three times worse a ratio for the same 10x size step. Over the full 100x range
(R=100→10,000), admission cost grew **~15x** and evidence cost (`fast_vet`: `--fast` still
runs `go vet ./...` regardless of the `[reification]` flag) grew **~53x**. Both are still
sub-linear in the strict sense (15x and 53x are both less than the 100x size increase), but
neither is a stable exponent — the growth *rate* itself increased at larger R for both
measures, and this data does not support extrapolating the first-decade ratio to
arbitrarily large repositories. Report as measured: real, substantial sub-linear scaling
with a decaying advantage, not "flat."

**F2b — What does hold up, and gets *better* with scale: admission stays proportionally
far cheaper than evidence.** The evidence-to-admission cost ratio (D-averaged) was 3.62x at
R=100, 6.12x at R=1,000, and **12.75x at R=10,000** — admission's relative cheapness
*increased* with repository size even though its absolute cost also grew. That is the more
defensible form of this session's thesis at 100x scale: not "admission cost is flat," but
"admission cost grows markedly slower than the evidence cost it gates," and that gap widens,
not narrows, as the repository gets larger.

| D | R=100 admission median | R=1000 admission median | R=10000 admission median | R=100 fast_vet median | R=1000 fast_vet median | R=10000 fast_vet median |
|---|---|---|---|---|---|---|
| 0 | 116.5ms | 267.7ms | 1,774.8ms | 444.1ms | 1,685.5ms | 22,661.3ms |
| 4 | 116.1ms | 254.5ms | 1,611.5ms | 383.0ms | 1,595.0ms | 24,501.3ms |
| 16 | 128.2ms | 292.6ms | 2,041.3ms | 477.7ms | 1,702.3ms | 22,028.5ms |

D=64 is excluded from R=100 (the 40%-selection-ratio fallback fires there, per F3) but is
present at R=1,000 (323.8ms admission / 1,683.6ms fast_vet) and R=10,000 (2,218.8ms
admission / 21,800.8ms fast_vet) — a 6.85x admission ratio and 12.95x fast_vet ratio for
that one available decade, consistent with the other three D levels.

**F3 — The 40% test-selection fallback is itself repository-size-dependent, and it fired
exactly where the design predicted.** At R=100, D=64's 65 affected tests are ~65% of the
~100-file test suite, so Nool's own `max_selected_ratio = 0.4` guard falls back to the full
suite and the `affected-tests` probe's output format changes shape (the cell is correctly
excluded from the scaling fit, not silently averaged in — see `excluded` in the results
file). At R=1,000 the same 65 tests are ~6.5% of the suite, the fallback does not fire, and
the closure probe matches ground truth exactly. This is not a bug in D=64; it is the ratio
guard behaving exactly as documented, and it is itself evidence that "assurance cost" is not
a single number — it depends on repo size in more than one place.

**F4 — On real production data, the picture is dominated by cold-process cost, not the
admission logic.** `b10_self` replayed the touched-path sets of this session's own last 30
landed knots (a live ~860-file, 1,200+-knot Rust repository) as gate-only propose calls
against a one-shot scratch copy. All 30 measured cleanly, 0 refused. Envelope
affected/declared ratio: median 19.2x, p90 39x, max 87.5x — real hub-file changes (files like
`propose_cmd.rs`, `engine.rs`) touch a large, heavy-tailed closure. `evidence_plan` correctly
routed 19 of 30 (63%) to `HumanApproval` for touching a `[steer] sensitive_path`
(`aram`/`auth`/`billing`/`harness-api`/`identity`) or a Deny-band gate score, and 11 to
`PackageTests`. But `blast_ms` (computing the envelope) had a median of 3.7s and `aram_ms`
(WASM policy evaluation) a near-constant ~1.4s per call — both are cold-process costs on a
fresh, uncached scratch copy (SQLite pages never touched, Wasmtime JIT-compiling policy
modules from scratch), not the steady-state cost of a warm, long-running process. A follow-up
against a warm copy (or the live daemon) is needed to separate "genuinely O(R)" from
"one-time cold start," and F2's synthetic numbers above are the cleaner signal for the
scaling question specifically because the fixture is built fresh at every R, so the cold-start
term is present at both R=100 and R=1,000 and mostly cancels out of the ratio.

## What is built and what remains

| Part | Status | What it can claim |
|---|---|---|
| `b10_self` | Built, run (30/30 knots) | Real envelope/plan/contracts distributions on a real repository; real evidence-plan routing; a raw (not scaling-corrected) cold-cost profile |
| `b10_asymptotic` | Built, run at R ∈ {100, 1,000, 10,000} | The scaling ratios in F2/F2b/F3 above, with ground truth verified by construction and mismatches excluded rather than averaged in |
| `b10_oss` (a real 10–50 kLOC OSS Go service) | Not started | Same design as `b10_self`, pointed at a third-party repository instead of Nool's own |
| N-concurrency cell, unknown-path cell | Not built | In the original pre-registration; deferred |

**Note on the R=10,000 run:** the first two attempts at this tier (600s and 1,800s init
timeouts) did not complete — not a resource crash (CPU/memory stayed healthy throughout),
but `nool init`'s own bootstrap step genuinely exceeding both budgets on a 20,001-file
repository. A third attempt at a 3,600s budget succeeded and produced the R=10,000 data
above. That slow bootstrap is a separate, real defect from the admission-cost question this
benchmark measures — filed and fixed as bug 589673de in the Nool product repo (a
mutex-shared discovery cache replacing a per-file `Ledger::open`, plus phase-level
resumability so a killed `init` no longer has to restart from zero) — and is not itself
part of the C(R,S) admission-cost measurement, since `b10_assurance_scaling` measures
steady-state `propose` cost *after* `nool init` has already built the entity graph.

## Methodology notes and known pitfalls

- **`--fast` is not gate-only for a compiled file.** It always materializes and runs the
  native integrity driver, never consulting `[reification].enabled` — that flag is checked
  only when mode is not Fast. `--full` + `[reification] enabled = false` is the actual
  admission-only combination. Verified at 0.1s on a throwaway 2-file repo before trusting it
  on anything real. Getting this wrong against the Nool product repo's own Rust workspace (not
  this Go fixture) triggered a cold `cargo check` that ran the scratch disk to zero — see the
  README's B10 section for the full story.
- **Ground truth is checked, not assumed**, per D and R: `probe_one()` compares the reported
  affected-test count against the value the fixture generator computed by construction; a
  mismatch excludes that cell from the scaling fit (`excluded` in the results JSON) rather
  than silently degrading the fit.
- **Reps are small (3)** for this first data — enough to see the direction and magnitude of
  the effect at each of the three R levels (100, 1,000, 10,000), not enough for tight
  confidence intervals. Treat the ratios above as a first measurement to be tightened, not a
  final number, and note that the R=10,000 tier is a single run (not yet repeated across
  separate fixture builds), unlike R=100/1,000 which this session's earlier runs also
  measured once each.
