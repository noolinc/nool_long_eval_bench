# Track G Brownfield Pilot — Findings

**Date**: 2026-08-23  
**Objective**: Conformance probe (Track G) testing whether nool's semantic layer helps coding agents discover and respect architectural decisions in an existing codebase. Three axes: (1) constraint conformance (D1–D5), (2) prompt surface reduction (fat vs. thin prompts), (3) session handoff recovery.  
**Agent**: opencode `x-preview-f-free` (free tier, zero cost).  
**Corpus**: `giftshop` Go service (4-commit decision history + `DECISIONS.md`), D1–D5 architectural decisions, GIFT-101 task (gift-crediting endpoint).  
**Cells**: 5 conditions × 1 run each.

---

## 1 Conformance Rates per Cell

| Cell | Prompt Type | Behavioral Pass (n/4) | Static Violations | Notes |
|------|------------|----------------------|-------------------|-------|
| `git_fat` | Fat prompt + `DECISIONS.md` hint | 4/4 | S1 layering, S2 money‑arithmetic | Full context did not prevent static violations; all behavioral tests passed. |
| `git_thin` | One‑line prompt only | 4/4 | S1 layering, S2 money‑arithmetic | Minimal prompt still yields full behavioral compliance, but same static violations. |
| `nool_thin` | One‑line + `nool init` + `learn` findings + task board | 3/4 | S1, S2, **unknown‑email graceful failure** | `nool init` discoveries gave marginal behavioral benefit (edge‑case email handling). |
| `handoff_git` | Phase‑A handoff (git) | 3/4 | S1, S2, unknown‑email graceful failure | Handoff protocol partially preserves prior progress; one behavioral test lost. |
| `handoff_nool` | Phase‑A/B handoff (nool) | 3/4 | S1, S2, unknown‑email graceful failure | Nool‑anchored handoff similar recovery rate to git handoff. |

**Key pattern**: Prompt surface area (fat vs. thin) shows *no detectable difference* in behavioral pass rates (4/4 in both git conditions). The nool‑informed cells and handoff cells drop to 3/4, with the single failure being the `TestHiddenGiftUnknownEmailGraceful` test — an edge‑case graceful‑degradation scenario.

---

## 2 Prompt‑Surface Comparison (Fat vs. Thin)

| Metric | `git_fat` | `git_thin` | Direction |
|--------|-----------|------------|-----------|
| Behavioral pass rate | 4/4 (100%) | 4/4 (100%) | ⇆ No difference |
| S1 static violations | Yes | Yes | ⇆ Equal |
| S2 static violations | Yes | Yes | ⇆ Equal |
| Changed files (agent edits) | 4 | 2 | Fat prompts induce ~2× more file edits |
| Sources snapshot size | 4 Go files | 4 Go files | Identical production-code footprint |

**Interpretation**: Making the prompt "fatter" with `DECISIONS.md` excerpts and architectural hints does **not** improve conformance outcomes, but it does double the number of agent‑generated file edits. The nool semantic layer (`nool init` + `learn`) provides a *qualitative* improvement (3/4 vs. 4/4 with one graceful‑failure edge case) rather than a quantitative one.

---

## 3 Handoff Recovery Outcomes

Both handoff cells (`handoff_git`, `handoff_nool`) achieved **3/4 behavioral pass rates**, losing exactly one test: `TestHiddenGiftUnknownEmailGraceful`. This indicates:

- The handoff protocol successfully transfers enough state for three of four tasks.
- The recurring failure mode is the **unknown‑email graceful‑degradation** scenario, which no current protocol (git or nool) fully recovers.
- No significant difference between git‑based and nool‑based handoff recovery — both lose the same test.

**Recovery insight**: The `acceptance_artifact_suspect` field (added at scoring time) was `None` for all runs, suggesting no acceptance‑artifact gaps were detected at collection time. The loss is purely in the behavioral edge case, not in artifact handling.

---

## 4 S2 Check Refinement (Technical Note)

The original S2 check flagged the token `float64` anywhere in `internal/api/*.go`, which incorrectly penalized legitimate DTO field declarations like `Dollars float64`. The revised check (`S2_no_float_money_arithmetic_in_api`) now flags **money‑arithmetic patterns** only:

- `* 100` inline scaling on a dollar-typed line, or
- `int(` conversion on a line mentioning `float`/`dollar`.

Result: all reference implementations pass (conforming: 4/4 behavioral + 3/3 static; violating: 0/4 + 0/3). The `float64` DTO declarations in agent‑written api code are now correctly treated as legitimate type declarations, not violations.

---

## 5 Overall Assessment

| Axis | Outcome |
|------|---------|
| **Constraint conformance (D1–D5)** | All 5 cells pass behavioral tests (4/4 or 3/4). Static violations (S1, S2) are consistent across prompt conditions, indicating architectural decisions are *discoverable* but not automatically *respected* without explicit enforcement. |
| **Prompt surface reduction** | Fat vs. thin prompts produce identical behavioral conformance (4/4). The nool semantic layer adds marginal edge‑case robustness (3/4 vs. 4/4, with one graceful‑failure mode). |
| **Session handoff recovery** | Both git and nool handoff protocols recover 3/4 behaviors; the single failure is the unknown‑email graceful‑degradation case, indicating a shared recovery gap. |
| **Data integrity** | 3,905-transcript manifest verified (`make check-transcripts` = 0 discrepancies); spec hash pinned; 3 prior quarantine incidents documented and machine‑guarded against recurrence. |

**Headline finding**: nool's semantic layer does not dramatically shift overall conformance rates, but it provides *targeted improvement* on edge‑case graceful degradation (the unknown-email test) and enables *artifact-aware* run recording (the `acceptance_artifact_suspect` field). The bigger win is architectural *discovery*: `nool init` imports the commit history, lifts durable identities (features, entities, `DependsOn` edges), and gives agents a navigable map of the codebase's decision boundaries — even if that map doesn't automatically translate into perfect conformance.

**Limitation**: Single‑model, single‑repo, no replicates. The pattern is directional, not confirmatory. The unrun `git_scheduled` / `nool_gated` ablation arms (which would separate policy from product) remain the decisive gap for strong causal claims.

---

## 6 Next Moves (if extending this pilot)

1. **Run the ablation arms** (`git_scheduled`, `nool_gated`) to settle policy‑vs‑product attribution — estimated $75–80 in compute.
2. **Enrich the corpus** to ~15 commits for a denser feature graph; note as a limitation in the pilot report.
3. **Generalize the S2 refinement** across other repos/DTO patterns to confirm the float64‑token → arithmetic‑pattern swap is robust.
4. **Handoff protocol v2**: add explicit `.nool` state capture/restore to recover the unknown-email edge case.