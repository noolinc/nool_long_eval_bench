# Invalidated runs: spec 8c rerun attempts, git_gated_queue reps 3-4,
# corpus v3, N=35 (2026-08-22 16:09-16:11 UTC)

Two run records are **excluded** from the spec §8c arm-decomposition study
and from `results/trackc/fleet_runs.jsonl`:

- `fleet_git_gated_queue_d15731ef` (2/60 accepted, $0.38 total, 53/60
  zero-cost tickets, wall ~114 s)
- `fleet_git_gated_queue_2f4d8ca9` (0/60 accepted, $0.00 total, 60/60
  zero-cost tickets, wall ~113 s)

These were the first rerun attempts of the runs left outstanding by the
2026-08-22 session-limit incident
(`../invalidated_2026-08-22_session-limit-midrun/`). The operator account's
usage limit was hit again mid-batch and the batch ran to completion in a
stuck state instead of failing fast.

## Cause

Identical signature to both prior incidents, confirmed directly in the
transcripts (e.g. `results/trackc/transcripts/fleet_git_gated_queue_d15731ef_t1.jsonl`,
`..._2f4d8ca9_t3.jsonl`):

```
"api_error_status": 429
"error": "rate_limit"
"rate_limit_event"
```

— instant rejections before any billed work. Clean sibling runs in this
study cost ~$6.85-7.30 with zero zero-cost tickets and ~130-350 s wall;
both excluded runs are far outside that envelope on every axis.

## Detection

Same tell as documented in the 2026-08-22 NOTE: acceptance/cost far below
every sibling run in the batch, zero-cost tickets clustered rather than
spread across genuinely-hard tickets; 429/rate_limit confirmed in raw
transcripts.

## Disposition

- Raw records preserved verbatim, one JSON file per run, in this directory.
- Removed from `results/trackc/fleet_runs.jsonl`; the committed file holds
  only clean runs.
- Transcripts retained on disk (covered by
  `results/trackc/transcripts_manifest.jsonl`).
- **Still outstanding from spec 8c:** git_scheduled rep 3, nool_gated rep
  3, and all three arms for reps 4-5, PLUS this incident's target:
  git_gated_queue reps 3-5 clean reruns — i.e. the §8c replication is
  further behind than the prior NOTE stated. Verify account usage headroom
  AND set a fail-fast guard on per-agent cost (a $0.00 agent result must
  abort the batch, not continue) before the next attempt.
