# nool_fleet N=25 rerun against nool 7.8.0

**Status:** complete (2 reps) · 2026-09-16
**Context:** the N=25 concurrency-ladder point in `docs/findings/2026-08-23-findings.md`
§6 was collected against nool 6.14.1. Since then the product has landed a full
incremental-admission-control rework and a resumable `nool init`
(`docs/CHANGELOG.md` 7.8.0). This reruns only the `nool_fleet` arm at the same
N=25, same 60-ticket v3.1 corpus, same model (claude-sonnet-5), against the
current 7.8.0 release — the `git_fleet` arm is not re-run, since git's
behavior does not depend on the nool version under test; its original
6.14.1-era N=25 records (`fleet_git_fleet_71ab28f3`, `fleet_git_fleet_a7499905`)
are reused unchanged for the comparison below.

## Result

| Run | Version | Accepted | Wall | Cost |
|---|---|---|---|---|
| git_fleet rep 1 (reused, 6.14.1) | 6.14.1 | 41/60 (68%) | 257s | $10.61 |
| git_fleet rep 2 (reused, 6.14.1) | 6.14.1 | 40/60 (67%) | 132s | $9.74 |
| nool_fleet rep 1 (this run) | 7.8.0 | 59/60 (98%) | 309s | $6.41 |
| nool_fleet rep 2 (this run) | 7.8.0 | 59/60 (98%) | 343s | $6.16 |

nool_fleet held zero merge conflicts in both reps at N=25 on 7.8.0, the same
result the 6.14.1 study reported at this point on the ladder — the
coordination-layer property this benchmark exists to test is unchanged across
this many product versions and a full architectural rework of the propose-time
gate. Both reps landed at **$6.1644 and $6.4068**, roughly **35-40% cheaper**
than the reused 6.14.1 git_fleet runs, consistent with fewer wasted
agent-turns fixing merge damage.

## Honest deviation from the historical 60/60, 60/60

The original 6.14.1 study reported nool_fleet at a perfect 60/60 in both N=25
reps. This rerun did not reproduce that: **59/60 in both reps**, and the
*same* ticket (`t21`) failed both times. This is reported as measured, not
rounded up to "still 60/60" or glossed over.

What t21's failure was *not*: not a merge conflict, not a build break, not a
smoke-test failure, not an agent timeout or error. `final_health` was
`{build_ok: true, smoke_ok: true}` in both reps, the merge integration record
shows a clean landing (`clean: true, exit_code: 0, queue_rejected: false`) with
zero co-changed files at symbol level, and the agent itself exited 0 with no
error in both reps (7 turns rep 1, 10 turns rep 2). What actually failed was
t21's own hidden acceptance test (`go test ./accept/t21/`) — the agent's
implementation was functionally wrong for that specific ticket, consistently,
across two independent reps.

This points at a task-difficulty / model-behavior effect specific to ticket
t21 under claude-sonnet-5, not a nool coordination regression: the mechanism
this benchmark is actually measuring (does the fleet arm avoid interfering
merges) shows no change from 6.14.1. A single ticket failing identically
twice is also consistent with a genuinely ambiguous or under-specified ticket
in the v3.1 corpus rather than noise — worth a manual look at `tickets_v3.json`'s
t21 definition before the next ladder point, but out of scope for this rerun.

## Infrastructure notes from this run

- **Stale daemon zombies blocked launch.** 184 `nool-daemon` processes with
  dead sockets (harmless individually, `pgrep -f nool-daemon` still trips the
  harness's stale-daemon preflight refusal) had accumulated on the runner
  machine. Cleared with a targeted kill of every PID except the one
  `nool daemon status` reported healthy.
- **A harness bug, not a nool bug, blocked launch even after that.**
  `preflight_isolation()` in `harness/fleet_run.py` parsed `nool daemon status
  --all --json` by taking the first line starting with `{` and calling
  `json.loads` on it alone. That command's `--json` output is pretty-printed
  (multi-line) on current nool, so the lone `{` line always failed to parse
  (`Expecting property name enclosed in double quotes: line 1 column 2`),
  permanently refusing to launch while any daemon was running — which is
  effectively always, once a machine's identity key exists. Fixed to parse
  from the first `{` to the end of stdout instead (knot landed this session).
- **The shared daemon auto-attaches to any repo a nool command touches**,
  including a fresh temp workspace `fleet_run.py` creates per invocation —
  tripping the harness's *other* preflight check (a live daemon watching a
  workspace under the run's roots). Stopped the daemon entirely
  (`nool daemon stop --all`) for the run's duration rather than chasing each
  new temp directory; safe here because `nool init`'s daemon-autostart only
  fires on a machine's first-ever init, which had already happened.
- **N=25 is genuinely RAM-intensive.** The runner machine (16GB) dropped to
  ~600MB free during the initial 25-worker launch ramp before recovering to
  ~2-3GB free once early tickets completed and their processes exited; macOS
  leaned on ~2GB of swap during the trough. The 2026-08-22-era launch-cadence
  stagger fix (1.5s between worker launches) is still in place and load-bearing
  — this did not reproduce the original "RAM exhausted within ~9s" failure,
  but the machine was close to it.

## Reproduction

```
python3 harness/fleet_run.py --model claude-sonnet-5 \
  --arms nool_fleet --workers 25 --tickets tickets_v3.json --reps 2
```

Raw records: `results/trackc/fleet_runs.jsonl` (run ids
`fleet_nool_fleet_35da22d2`, `fleet_nool_fleet_ffb4fd88`), transcripts under
`results/trackc/transcripts/fleet_nool_fleet_{35da22d2,ffb4fd88}_*.jsonl`.
