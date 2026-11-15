# B12: revalidation and quarantine rates across an agent and overlap ladder

Date: 2026-11-15. Nool task f36857ee (architecture review 2026-10-20, experiment 5). Probe:
`micro/b12_revalidation_ladder.py`. Results: `results/micro/b12_revalidation_ladder_modify.json`
(primary) and `results/micro/b12_revalidation_ladder_create.json`.

## Question

When a seal finds that knots landed since a candidate was validated, it either trusts the recorded
Full verdict (`validation:region-fresh`) or re-runs validation first (`validation:region-revalidated`).
Candidates that can never seal are quarantined. How often does each happen as agent count and overlap
grow, and what did task 90280876 (knot 45fbeb4e) change? That task added the forward dependency
closure of the declared paths to the stale region.

## Method

There is no LLM in this probe. N scripted writers land governed changes (`propose --full --solidify`,
one `--as-agent` identity each) concurrently in ONE nool workspace built from the fleet_service Go
starter. Every seal therefore races other seals.

- **Providers:** min(3, N) writers, one each on `store/memstore.go`, `util/ids.go` and `util/clock.go`.
  Each loops "append one exported func, land it" until every consumer is done, so the dependency
  files keep changing while consumers seal.
- **Consumers:** N − 3 writers, each owning `ext/w<i>/w.go`. Overlap is the share of consumers whose
  file calls into a provider's file: low 0%, medium 50%, high 100%.
- **Designs:**
  - *modify* (primary): every consumer file is landed and indexed in the base, and the consumer
    appends one func to it. This isolates the dependency walk.
  - *create*: every consumer lands a new file.
- **Retries:** a writer retries exit 3 (contention, "safe to retry") up to three times. The create run
  predates this and did not retry.
- **Treatment:** one benchmark-only build of nool 7.28.0 (HEAD 3cce6870d plus a 3-line,
  never-landed patch). With `NOOL_BENCH_REVERSE_ONLY=1` set, the stale region walks only the
  dependents of the declared paths, which was the behaviour **before** 90280876. With it unset, the
  region also walks the forward closure, the behaviour **after** that task. Both arms run the same
  binary.
- **Cells:** N ∈ {10, 25, 50} × overlap ∈ {low, medium, high} × arm ∈ {before, after}, with one
  repetition per cell.

## Results: modify design (primary)

| N | overlap | arm | landed / proposals | revalidation share | consumers revalidated | providers revalidated | quarantined | refused | seals/hour | s per landed ticket |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | low | before | 17/17 | 0.000 | 0/7 | 0/10 | 0 | 0 | 3203 | 1.12 |
| 10 | low | after | 13/13 | 0.000 | 0/7 | 0/6 | 0 | 0 | 3265 | 1.10 |
| 10 | medium | before | 17/17 | 0.118 | 0/7 | 2/10 | 0 | 0 | 2998 | 1.20 |
| 10 | medium | after | 16/16 | 0.062 | 0/7 | 1/9 | 0 | 0 | 3167 | 1.14 |
| 10 | high | before | 17/17 | 0.059 | 0/7 | 1/10 | 0 | 0 | 3024 | 1.19 |
| 10 | high | after | 16/16 | 0.312 | 2/7 | 3/9 | 0 | 0 | 3110 | 1.16 |
| 25 | low | before | 38/38 | 0.000 | 0/22 | 0/16 | 0 | 0 | 3193 | 1.13 |
| 25 | low | after | 34/34 | 0.000 | 0/22 | 0/12 | 0 | 0 | 3221 | 1.12 |
| 25 | medium | before | 33/33 | 0.061 | 0/22 | 2/11 | 0 | 0 | 3013 | 1.19 |
| 25 | medium | after | 30/30 | 0.033 | 0/22 | 1/8 | 0 | 0 | 3189 | 1.13 |
| 25 | high | before | 31/31 | 0.065 | 0/22 | 2/9 | 0 | 0 | 3044 | 1.18 |
| 25 | high | after | 36/36 | 0.194 | 3/22 | 4/14 | 0 | 0 | 2688 | 1.34 |
| 50 | low | before | 58/58 | 0.000 | 0/47 | 0/11 | 0 | 0 | 2853 | 1.26 |
| 50 | low | after | 55/55 | 0.000 | 0/47 | 0/8 | 0 | 0 | 2938 | 1.23 |
| 50 | medium | before | 54/54 | 0.019 | 0/47 | 1/7 | 0 | 0 | 2893 | 1.24 |
| 50 | medium | after | 59/59 | 0.220 | 10/47 | 3/12 | 0 | 0 | 2693 | 1.34 |
| 50 | high | before | 60/60 | 0.033 | 0/47 | 2/13 | 0 | 0 | 2772 | 1.30 |
| 50 | high | after | 55/55 | 0.055 | 1/47 | 2/8 | 0 | 0 | 2811 | 1.28 |

Across the whole run, writers retried a contention exit six times in total, and no proposal was
still refused after its retries. In every cell the final tree builds (`go build ./...`).

## Results: create design

| N | overlap | before: revalidation share (consumers) | after: revalidation share (consumers) | refused before / after (no retries) |
|---|---|---|---|---|
| 10 | low | 0.33 (0.80) | 0.27 (1.00) | 2/14, 3/18 |
| 10 | medium | 0.40 (0.75) | 0.38 (0.75) | 3/13, 4/12 |
| 10 | high | 0.56 (0.75) | 0.46 (0.80) | 3/12, 3/14 |
| 25 | low | 0.48 (0.93) | 0.63 (0.94) | 7/36, 6/30 |
| 25 | medium | 0.72 (0.92) | 0.50 (0.92) | 10/28, 10/34 |
| 25 | high | 0.64 (0.90) | 0.71 (0.90) | 13/27, 12/29 |
| 50 | low | 0.63 (0.96) | 0.71 (0.96) | 20/61, 24/55 |
| 50 | medium | 0.74 (0.96) | 0.68 (0.95) | 21/56, 26/60 |
| 50 | high | 0.67 (0.95) | 0.75 (0.96) | 28/58, 25/57 |

No candidate was quarantined in any cell of either design.

## Findings

1. **Before vs after 90280876 (forward closure):** in the modify design, no consumer was revalidated
   in any "before" cell (0 of 228 consumer seals). The reverse-only region cannot see a dependency
   that changed under a consumer. With the forward closure ("after"):
   - consumers whose dependency changed concurrently were revalidated in 4 of 6 medium and high
     cells (16 of 228 consumer seals, up to 21% of the consumers in a cell);
   - low-overlap consumers, which have no corpus edge, stayed at 0 revalidations, as they should.

   The forward closure adds revalidation exactly where a candidate's dependencies moved. It costs
   about 0–12% of seals per hour in those cells. That figure is within run-to-run noise at one
   repetition on a loaded machine.
2. **Revalidation share stays low when files are already indexed.** The share is 0 at low overlap
   and at most 0.31 at medium and high, with no growth trend from N=10 to N=50. Provider seals, which
   have many dependents, account for most of it in both arms.
3. **Quarantine share is 0 everywhere.** In the modify design no proposal failed once writers retried
   exit 3 up to three times (six retries in the whole run).
4. **New files dominate revalidation and contention.** A new file has no indexed entity, so the region
   rule's new-file condition (spec 2026-11-11, condition 2) treats every concurrently touched path as
   stale. In the create design, 75–96% of consumer seals were revalidated, independent of overlap
   and arm. Without retries, 14–48% of proposals ended in the contention exit ("knots touching this
   candidate's region landed while it was validated"), and the rate grew with N. For fleets whose
   tickets mostly add files, this condition, not the dependency walk, sets revalidation and retry
   rates. An import-aware region for new files is the lever if that cost matters.

## Limits

- **One repetition per cell.** The cell-to-cell differences in the medium and high "after" cells
  (for example N=50 medium with 10 consumers revalidated, N=50 high with 1) depend on whether a
  provider landed between a consumer's ghost run and its seal. That timing varies run to run.
- **Loaded machine.** Load was 1.9–2.3 per core, from another session's cargo build and a paired
  nool-code eval running alongside. The build was a debug build. Absolute seals per hour are lower
  than a release build on a quiet machine would show, and they compare only within this run.
- **Lock wait was not measured.** `lock_wait_ms` exists only in the opt-in analytics payload, and
  analytics was disabled. The binary prints no lock wait.
- **"Cost per landed ticket" is reported as seconds per landed ticket.** Scripted writers spend no
  tokens.
- **Treatment, not history.** The "before" arm reproduces 90280876's change by switching off the
  forward walk on today's HEAD. It does not replay the October binary, so later changes to the region
  rule (task 627e3144, the new-file condition) are present in both arms.
- **Small corpus.** It has 13 base files, three dependency files and Go only.

## Reproduce

```
# build the benchmark-only binary: apply micro/b12_reverse_only.patch to
# nool HEAD and run `cargo build -p nool --bin nool`
cd micro && PATH=<dir with that nool>:$PATH B12_DESIGN=modify python3 b12_revalidation_ladder.py
B12_DESIGN=create B12_N=10 B12_OVERLAP=high ...   # narrower cells
```

## Follow-up: new-file region fixed (Nool knot 26dc4fd8)

Finding 4 led to a fix the same day. The seal now reads a new file's dependencies from its source
(`seal_graph::source_dependencies`). Its imports are walked forward, and its Go and Java package
siblings are walked both ways, so the package's importers count as its dependents. The blanket
"every concurrent path is stale" rule now applies only when the source cannot be read or is
generated.

The create design was rerun on a build of that fix, "after" arm only. Results are in
`results/micro/b12_revalidation_ladder_create_fixed.json`. Writers in the rerun retry exit 3 up to
three times; the original create run did not, and the rerun needed 0–1 retries per cell.

| N | overlap | revalidation share, before → after fix | consumers revalidated, before → after | refused, before → after |
|---|---|---|---|---|
| 10 | low | 0.27 → 0.00 | 4/4 → 0/7 | 3/18 → 0/14 |
| 10 | medium | 0.38 → 0.06 | 3/4 → 0/7 | 4/12 → 0/16 |
| 10 | high | 0.46 → 0.25 | 4/5 → 2/7 | 3/14 → 0/16 |
| 25 | low | 0.63 → 0.00 | 15/16 → 0/22 | 6/30 → 0/35 |
| 25 | medium | 0.50 → 0.08 | 11/12 → 1/22 | 10/34 → 0/38 |
| 25 | high | 0.71 → 0.21 | 9/10 → 4/22 | 12/29 → 0/28 |
| 50 | low | 0.71 → 0.00 | 22/23 → 0/47 | 24/55 → 0/55 |
| 50 | medium | 0.68 → 0.09 | 20/21 → 4/47 | 26/60 → 1/55 |
| 50 | high | 0.75 → 0.22 | 22/23 → 10/46 | 25/57 → 2/53 |

After the fix, new files behave like edited ones. They are revalidated only when a file they import
landed in between, and they are never revalidated at low overlap. Every final tree still builds.
The machine was loaded during the rerun (3.2 per core), so compare shares, not seals per hour.
