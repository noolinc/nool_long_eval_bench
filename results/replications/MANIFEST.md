# Replication manifest

Every run's own JSON carries its full provenance block; this manifest indexes
the experiment-level conditions for cross-run comparison.

| Condition | Run 1 | Run 2 |
|---|---|---|
| Date (UTC) | 2026-08-20 (17:11–18:55) | 2026-08-20 (19:07–) |
| nool | 6.13.0 | **6.14.0** (upgraded between runs) |
| git | 2.50.1 (Apple Git-155) | 2.50.1 (Apple Git-155) |
| go | 1.26.2 darwin/arm64 | 1.26.2 darwin/arm64 |
| Claude Code CLI | 2.1.237 | 2.1.237 |
| Model (all LLM cells) | claude-sonnet-5 | claude-sonnet-5 |
| Python | 3.11.2 | 3.11.2 |
| Platform | macOS 26.5.2 arm64 | macOS 26.5.2 arm64 |
| Execution | local, adapter isolation `--setting-sources project,local` | same |

**Run 2 is a cross-version re-test, not a same-conditions replication** —
nool moved 6.13.0 → 6.14.0 between runs (caught by provenance stamping).

Data locations:
- Track B run 1: `run1_micro_2026-08-20/` (snapshot). Track B run 2:
  `../micro/` (current).
- Track C and D runs append to `../trackc/runs.jsonl` and
  `../trackc/fleet_runs.jsonl`; runs are distinguished by `started_utc`
  and per-record version fields.

**Run 2 LLM outcomes (completed 19:44 UTC):** Track C grid 20/20 hidden-test
pass (run 1: 19/20; run 1's single failure was a multi_nool inter-agent
interface mismatch, not reproduced); token/turn medians stable within noise
in every cell; still no arm separation on any metric. Fleet pilot: both arms
8/8 accepted, zero conflicts, both runs; nool gating wall-time overhead
+10 s in run 1, +3 s in run 2. Effect directions fully consistent across
runs.

**Cross-version replication of the four bounding findings (Track B):**
B5 semantic-layer-classifies-but-file-merge-conflicts: identical
(1 clean / 14 conflicts, sem-pass 15/15, all reps, both versions).
B7 bisect names first post-good knot instead of culprit: identical.
B3 pluck destroys later unrelated work (both timeline variants): identical.
B4 parseable test-breaking change accepted through propose + deferred
validation: identical.

## Run 3 scale-up 1 (2026-08-21, nool 6.14.1, CLI 2.1.238, claude-sonnet-5)

Track D at N=10 workers, corpus v2 (20 tickets, function-level contention
clusters A/B/C). Primary comparison, all on nool 6.14.1 with serialized
worktree creation and the fixed dispatch gate:
git_fleet 9a6eb70f (1/20 accepted; t17 clean-merge broke build, voiding 13
landed tickets), git_fleet 803f2288 (13/20; 7 cluster conflicts);
nool_fleet cb7ccf72 and 2a51582f (both 19/20, 20/20 clean merges, main
green; shared t2 failure is a pilot-era acceptance-test tolerance artifact
that fires only when all of cluster A lands).
Labeled variants excluded from the primary comparison: nool_fleet 16e2e1b0
(18/20, ran with the same-batch dispatch-gate hole), git_fleet 70dff997
(15/20, collected on nool 6.14.0 before the version bump).
Lost runs, no records: one git rep to a concurrent-worktree-add race, one
to operator-machine memory exhaustion; later runs sequential under a
memory watchdog. Raw records: results/trackc/fleet_runs.jsonl.

**B4 governance-path measurement (2026-08-21, nool 6.14.1):** B4 re-run
with three arms — git control, nool default governed path
(`propose --solidify`, full validation), nool relaxed path
(`propose --fast --solidify`). Governed path rejects both the
syntax-broken and the test-breaking change at propose; fast path rejects
syntax-broken only and accepts test-breaking with a project-integrity
warning at deferred validate; git accepts all three. This reinterprets the
run-1/2 "B4 accepted" rows above: those runs exercised only the `--fast`
path. Raw: `results/micro/b4_guardrails.json` (provenance 06:16 UTC).

**Corpus v2.1 (2026-08-21):** t2's acceptance test rewritten as property
checks routed through the service's own functions — the v2 version
hard-coded the 880-cent total and failed whenever cluster A's t10
processing fee had landed, the tolerance artifact noted under Run 3.
Verified green against both plain-starter and full-cluster-A Invoice
semantics before landing. `tickets_v2.json` bumped to corpus "v2.1";
ticket specs unchanged.

## Run 4 scale-up 1 confirmation (2026-08-21, corpus v2.1, nool 6.14.1, CLI 2.1.238, claude-sonnet-5)

Pre-registered confirmation quartet at N=10 on corpus v2.1:
git_fleet f39cb295 (12/20) and a3d8d322 (13/20) — bimodal good mode both
reps, cluster 2nd/3rd-merge conflicts, final health green, no
build-poisoning rep; matches the prediction (at or below 13/20).
nool_fleet 05bd48e0 (19/20, t2 only) and fd169904 (18/20, t2 + t10).
Prediction "nool 20/20 per rep" FALSIFIED — cause traced to a v2.1 test
artifact: t2's property test pinned one floor reading, the discounted
subtotal floored (999 at 20% -> 799), while every failing implementation
chose the other, discount amount floored (999 - 199 -> 800); both satisfy
the spec text "apply the percentage discount (round down)". t2 failed in
all four runs, both arms; git reps had passed t2 on v2, whose hard-coded
totals happened to match the pre-cluster semantics. Corpus v2.2 corrects
the rounding check to admit both readings, validated green against the
2x2 matrix of floor reading x plain / full-cluster-A Invoice. nool
fd169904's t10 failure is agent-quality (serialized dispatch, clean
merge, semantic miss). Raw: results/trackc/fleet_runs.jsonl.

## Track B cross-version reruns (2026-09-16 nool 7.8.0; 2026-10-12 nool 7.19.0)

Both reruns overwrite `../micro/b1..b9*.json` in place; the per-version
snapshot is the landing commit, not a directory:

| Condition | 7.8.0 run | 7.19.0 run |
|---|---|---|
| Landing commit | `1dd90c3` | `fee5c83` |
| Date (UTC) | 2026-09-16 (07:18–07:22) | 2026-10-12 (18:56–19:02) |
| nool | 7.8.0 | 7.19.0 (release binary, sha256 `d161c3f1…`, build `1fb8ed48`, clean) |
| Load per core (1 min) | 0.17–0.28, `quiet: true` on every file | 0.22–0.37, `quiet: true` on every file |
| B10 fixture | exponential fillers (pre-`5b66a0bc`) | B1–B9 unaffected; B10 smoke rerun on the fixed fixture, see below |

Recover a snapshot with `git show 1dd90c3:results/micro/b2_concurrency.json`.
Every correctness, precision, recall, false-positive and merge cell is
identical between the two runs; timings moved 5–15% in both the nool and the
git control arms (environment), with two cells beyond that drift (B1 hook
latency +3.3 ms on every hook; B2 `nool_n15` op median +33%) filed as Nool
task `c0cf9bb3`. Full comparison:
`../../docs/findings/2026-10-12-trackb-7.19.0-rerun.md`.

**B10 smoke on 7.19.0 (2026-10-12, `work/b10_sanity/`, not `results/`):** the
first attempt ran under load 19.8 because the fixture's filler packages were a
cross-package Fibonacci and `go test ./...` never finished (bug `b0d15306`,
fixed in `5b66a0bc`); the rerun on the fixed fixture was quiet (0.28/core),
warm-up 30.3 s, both cells exact selection with an intact closure.

## Incident index

- `results/trackc/invalidated_2026-08-20_user-config-contamination/` —
  early batch without adapter environment isolation.
- `results/trackc/invalidated_2026-08-21_rate-limit-midrun/` — provider
  limit reset mid-run; rest of batch completed clean.
- `results/trackc/invalidated_2026-08-22_session-limit-midrun/` — session
  limit never reset mid-batch; spec 8c reps 3(partial)-5 excluded.
- `results/trackc/invalidated_2026-08-23_token-limit-midrun/` — first
  rerun attempt of the outstanding 8c runs hit the limit again;
  2 git_gated_queue records excluded. Recurrence is now machine-guarded:
  `harness/fleet_run.py` scans every agent transcript for 429/rate-limit
  signatures and aborts the batch before any record is written
  (`RateLimitAbort`).
