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
