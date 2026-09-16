# B10 status: admission cost vs repository size and change surface

**Status:** first data, two of three planned parts built and run · 2026-09-16
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

**F2 — Admission cost is clearly sub-linear in repository size, but not flat by the
pre-registered 2x bar.** On the synthetic fixture (`b10_assurance_scaling`, R = 100 vs
R = 1,000 Go packages, three fan-in levels D = {0, 4, 16}, 3 reps each), the gate-only
admission median grew **2.19x–2.30x** for a **10x** increase in repository size. That is a
real, measurable win over proportional scaling, but it misses the `<= 2.0x` pass bar this
session pre-registered before running anything — report it as measured, not rounded down to
"flat." The evidence floor (`fast_vet`: `--fast` still runs `go vet ./...` regardless of the
`[reification]` flag) grew **3.56x–4.16x** over the same 10x — a clearly different, faster
regime, consistent with the thesis that admission and evidence are priced differently even
though neither is perfectly flat at this scale.

| D | R=100 admission median | R=1000 admission median | ratio | R=100 fast_vet median | R=1000 fast_vet median | ratio |
|---|---|---|---|---|---|---|
| 0 | 116.5ms | 267.7ms | 2.30x | 444.1ms | 1685.5ms | 3.79x |
| 4 | 116.1ms | 254.5ms | 2.19x | 383.0ms | 1595.0ms | 4.16x |
| 16 | 128.2ms | 292.6ms | 2.28x | 477.7ms | 1702.3ms | 3.56x |

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
| `b10_asymptotic` | Built, run at R ∈ {100, 1,000} | The scaling ratios in F2/F3 above, with ground truth verified by construction and mismatches excluded rather than averaged in |
| `b10_asymptotic` at R = 10,000 | Not run this session | `B10_R=100,1000,10000` is supported by the script; deferred for time, not for a known blocker — Go's toolchain is far lighter than this workspace's own Rust dependency tree, so this should be safe, but has not been verified at that scale |
| `b10_oss` (a real 10–50 kLOC OSS Go service) | Not started | Same design as `b10_self`, pointed at a third-party repository instead of Nool's own |
| N-concurrency cell, unknown-path cell | Not built | In the original pre-registration; deferred |

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
- **Reps are small (3) and R levels are two** (100, 1,000) for this first data — enough to see
  the direction and magnitude of the effect, not enough for tight confidence intervals. Treat
  the ratios above as a first measurement to be tightened, not a final number.
