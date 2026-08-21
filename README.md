# Nool Benchmark Suite

Reproducible benchmarks measuring whether [Nool](https://nool.dev) — a
semantic-agentic VCS and coordination layer for coding agents — materially
improves coding-agent outcomes versus plain git, across agent harnesses
(Claude Code first; Gemini CLI, Codex CLI, Pi via the same adapter contract).

**Design spec / pre-registration:**
`docs/superpowers/specs/2026-08-20-nool-benchmark-suite-design.md` —
hypotheses H1–H7 and the analysis plan were committed before any Tier 1 data
was collected. Read it before the numbers.

## Findings at a glance (runs 1–3 + fleet scale-up 1, 2026-08-20/21)

Full report with figures and provenance:
[`docs/findings/2026-08-21-findings.md`](docs/findings/2026-08-21-findings.md) ·
academic write-up: `docs/paper/2026-08-nool-fleet-study.md`. One pinned
model (claude-sonnet-5) throughout; product versions 6.13.0 → 6.14.1
recorded per run.

![Scale-up 1: tickets accepted per run](docs/findings/figures/trackd_acceptance.svg)

- **Fleet contention (pre-registered scale-up, 10 agents, 20 tickets,
  function-level contention):** uncoordinated git fleet accepted 1/20 and
  13/20 (in the 1/20 rep a textually-clean merge silently broke the build,
  voiding 13 landed tickets); nool's footprint-gated dispatch accepted
  19/20 in both reps with 20/20 clean merges and a green main throughout,
  at equal agent spend and +40–70% wall time. Spend per accepted ticket:
  $0.19–0.21 vs $0.30–3.80.
- **Mechanisms moved with the product:** on 6.14.1, contended merges
  converge 15/15 (were 1/15, = git, on ≤6.14.0), selective undo preserves
  later unrelated work 5/5 (was 0/5), and bisect names the true culprit.
  B4 clarified: the **default governed path rejects** test-breaking changes
  (full semantic validation); the **`--fast` relaxed path accepts** them as
  an explicit risk-control knob. Landing latency stays roughly 7–10× git.
- **Standing wins:** perfect write attribution under shared-workspace
  concurrency (git sweeps up to 56% of ops at N=15); context retrieval in
  163–408 bytes vs 660 for grep+read at small scale.
- **Honest nulls:** without designed contention (2×2 grid, 5-worker pilot,
  v1 corpus) the arms do not separate on any metric, in any run.

## Layout

| Path | What |
|---|---|
| `micro/` | Track B — deterministic mechanism micro-benchmarks (no LLM, no API keys, free to run) |
| `results/micro/` | Raw JSON output of Track B, committed with full provenance |
| `harness/` | Track C — LLM-in-the-loop 2×2 experiment harness; Track D fleet runner (`fleet_run.py`) |
| `tasks/` | Track C/D task catalogs (spec + starter + hidden held-out tests; fleet ticket corpora) |
| `results/trackc/` | Raw LLM-run records: 2×2 grid (`runs.jsonl`) and fleet runs (`fleet_runs.jsonl`) |
| `results/replications/` | Per-version Track B snapshots + `MANIFEST.md` indexing every run's conditions |
| `analysis/summarize.py` | Renders all committed results as tables. Numbers only — no conclusions in code |
| `analysis/make_figures.py` | Regenerates every figure in `docs/findings/` from the raw JSON |
| `docs/findings/` | Findings report with figures; `docs/paper/` holds the academic write-up |

Pre-suite pilot material (manual runs, no provenance — **not evidence**) was
archived and then removed from the working tree; it remains recoverable from
Knot DAG history (the `archive/` knots of 2026-08-20, including
`ARCHIVE.md`, which inventories it and explains why each item is excluded).

## Running Track B (anyone can, free)

Requirements: macOS/Linux, Python 3.11+, git, and the `nool` CLI on PATH
(version is recorded in each result's provenance block).

```bash
cd micro
python3 b1_overhead.py      # hook latency; propose/solidify vs add/commit
python3 b2_concurrency.py   # N concurrent writers, one shared workspace
python3 b3_recovery.py      # remove a bad landing, keep later unrelated work
python3 b4_guardrails.py    # broken/test-breaking commits vs a git control arm
python3 b5_swarm_merge.py   # N-branch merge: disjoint / same-anchor / diff-functions
python3 b6_context_retrieval.py       # semantic query vs grep+read baseline
python3 b7_regression_localization.py # nool debug bisect vs git bisect
python3 ../analysis/summarize.py
```

Each script builds isolated throwaway workspaces under the system temp dir,
times with monotonic clocks (ms), and writes one JSON file to
`results/micro/` including provenance (nool/git/python versions, platform,
timestamp). Re-running overwrites with your own provenance — replication
means comparing effect directions, not reproducing exact milliseconds.

Methodology notes that matter when reading results:

- Merge outcomes (B5) are detected from working-tree state (unmerged paths,
  conflict markers), never from exit codes; exit-code reliability is itself
  a recorded metric.
- B2's git arm counts a change as landed even when another writer's commit
  swept it in (`ops_swept_into_other_commit`) — attribution loss and landing
  are reported separately.
- B1's 100-file cell uses `--auto-justify` because nool's blast-radius gate
  blocks wide non-interactive proposes; the gate's existence is part of the
  result.
- B3 reports both a linear timeline and a thread-separated timeline for
  nool's `pluck` recovery path.

## Running Track C (LLM-in-the-loop; costs money)

Track C drives real agent CLIs headlessly over tasks in `tasks/`, in a 2×2
design (VCS: git|nool × mode: single|multi), N repetitions per cell, with the
**same pinned model in every cell** of an experiment. Hidden acceptance tests
are copied into the workspace only at scoring time.

```bash
cd harness
python3 run_experiment.py --harness claude --model <pinned-model-id> \
    --tasks redux_go --cells all --reps 5
```

The adapter records exact token counts, turns, and tool calls from the
harness's own accounting — estimated metrics are banned; anything a harness
does not expose is reported as null. See `harness/README.md` for the adapter
contract if you are adding gemini/codex/pi.

Current status: Track B complete on three product versions (6.13.0,
6.14.0, 6.14.1) with per-version snapshots under `results/replications/`.
Track C grid run three times (19/20, 20/20, 18/20; no arm separation).
Track D fleet: pilot plus pre-registered scale-up 1 complete (first arm
separation — see the findings report); next pre-registered step is the P1
concurrency ladder. External benchmark adaptations (CooperBench,
SlopCodeBench) are Tier 2 — see the spec.

## Threats to validity

Disclosed in the spec (§7) and repeated here: this is a vendor-run
evaluation, pre-registered to mitigate that; LLM cells at small N are
labeled underpowered; execution is currently local rather than containerized
(recorded in every provenance block); running nool arms requires a nool
license — external validators need the no-cost evaluation route described in
the spec (§8).

## License

Apache-2.0 — see `LICENSE` and `NOTICE`. You may use, modify, and
redistribute freely; redistributions must retain the attribution notices
(Nool, Inc.) per the license terms.
