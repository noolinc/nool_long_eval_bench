# Invalidated runs: spec 8c arm-decomposition study, rep 3 (partial) + reps 4-5 (full), corpus v3, N=35 (2026-08-22)

Eight run records are **excluded** from the spec §8c arm-decomposition
study and from `results/trackc/fleet_runs.jsonl`. They are not
measurements of any arm; they are an operator-account Claude session
usage-limit event that fired mid-batch and never cleared before the
batch finished.

- `fleet_git_scheduled_d8053317` (rep 3, git_scheduled) — **partially**
  contaminated: 16 of 60 agents hit the limit, 44 completed normally.
- `fleet_nool_gated_d8bd5036` (rep 3, nool_gated) — fully contaminated:
  60/60 agents hit the limit.
- `fleet_git_gated_queue_76b04017`, `fleet_git_scheduled_8d7f4430`,
  `fleet_nool_gated_8066404f` (rep 4, all three arms) — fully
  contaminated: 60/60 each.
- `fleet_git_gated_queue_ff545afc`, `fleet_git_scheduled_3c46a617`,
  `fleet_nool_gated_182d0782` (rep 5, all three arms) — fully
  contaminated: 60/60 each.

## Cause

Partway through rep 3 (after `git_gated_queue` completed cleanly, into
`git_scheduled`), the operator's Claude account hit its session usage
limit. Every affected agent subprocess's transcript shows the same
signature directly:

```
"result": "You've hit your session limit · resets 5:50pm (Europe/Berlin)"
"api_error_status": 429
"error": "rate_limit"
"total_cost_usd": 0
```

— an instant rejection before any billed work, not a genuine task
failure. This is the same signature as the 2026-08-21 incident
(`invalidated_2026-08-21_rate-limit-midrun/`), except that incident's
limit reset mid-run and the rest of the batch completed clean; this one
did not reset before `fleet_run.py`'s remaining loop iterations
(rep 3's `nool_gated` through all of reps 4-5) ran to completion, so
every subsequent arm×rep from that point on is a wall of instant
rejections — visible as `accepted 0/60 wall=~100s cost=$0` in the run
log, versus ~130-350s wall and ~$6.85-7.30 cost for every clean run in
this same batch.

Detected the same way as the prior incident: acceptance/cost far below
every sibling run in the batch, zero-cost tickets clustered rather than
spread, and `api_error_status: 429` / `rate_limit` confirmed directly in
the affected tickets' transcripts (e.g.
`results/trackc/transcripts/fleet_nool_gated_d8bd5036_t1.jsonl`).

## Disposition

- Raw records preserved verbatim, one JSON file per run, in this
  directory — never silently averaged into the spec 8c results.
- Removed from `results/trackc/fleet_runs.jsonl` before landing; that
  file now holds only the clean portion of this batch: rep 1 (all three
  arms, 60/60|60/60|39/60), rep 2 (all three arms, 60/60|60/60|39/60),
  and rep 3's `git_gated_queue` (38/60, a genuine merge-conflict result,
  not a rate-limit artifact — confirmed zero zero-cost tickets).
- **Remaining for a clean spec 8c rep 3-5:** rerun `git_scheduled` rep 3,
  `nool_gated` rep 3, and all three arms for reps 4 and 5 — 8 runs total
  — after confirming the account's session-limit reset time (5:50pm
  Europe/Berlin per the transcript above) has passed.
- General takeaway, same as 2026-08-21: verify account usage headroom
  before a multi-rep fleet batch that will make hundreds of API calls in
  one session; a sharp acceptance/cost drop with zero-cost tickets
  clustered together (rather than spread across genuinely-hard tickets)
  is the tell to check transcripts for `rate_limit_event` /
  `api_error_status: 429` before attributing it to either arm's gating
  behavior.
