# Invalidated run: nool_fleet rep 2, N=25, corpus v3 (2026-08-21)

`run_id: fleet_nool_fleet_f65e40dd` — recorded 44/60 accepted, wall 161s,
cost $7.30 — is **excluded** from the scale-up 2 N=25 point and from the
paper. It is not a measurement of either arm; it is an operator-account
Claude usage-limit event that fired mid-run.

## Cause

Partway through the run, the operator's Claude account hit its 5-hour
session usage limit (`"You've hit your session limit · resets 11pm
(Europe/Berlin)"`, `api_error_status: 429`,
`overageDisabledReason: "out_of_credits"`, `isUsingOverage: false`). From
that point, every subsequent ticket's agent subprocess received an
immediate rate-limit rejection instead of doing any work — visible as a
burst of `is_error: true` agents with implausibly short wall times (as
low as ~3.7s, 1 turn, 0 tokens) clustered together, rather than a spread
of genuine task failures. 19 of the run's 60 agents show this signature;
16 of the 16 acceptance failures are a subset of those 19.

Detected by inspecting individual agent transcripts
(`results/trackc/transcripts/fleet_nool_fleet_f65e40dd_t23.jsonl` shows
the `rate_limit_event` directly) after the acceptance rate (44/60) came
in far below both this run's own rep 1 (60/60) and the N=20 point's
nool_fleet reps (60/60, 60/60), with zero merge conflicts recorded —
ruling out an integration or gating failure and pointing at the agent
layer instead.

## Disposition

- Raw record preserved verbatim in `fleet_nool_fleet_f65e40dd.json`
  (this directory) for transparency; removed from the main
  `results/trackc/fleet_runs.jsonl` stream before landing, so it is never
  silently averaged into scale-up 2 results.
- Rerun as a clean nool_fleet rep 2 after confirming the reset time
  (21:00 UTC / 23:00 CEST) had passed; the clean rerun's record is what
  appears in `fleet_runs.jsonl` and the paper for N=25 nool_fleet rep 2.
- General takeaway for future runs: verify account usage headroom before
  a fleet run that will make dozens of API calls in one session, and
  treat a sharp acceptance drop with zero integration conflicts as a
  signal to check individual agent transcripts for `rate_limit_event`
  before attributing it to either arm.
