# Archive — pilot artifacts (pre-2026-08-20)

Everything in this directory predates the benchmark suite designed in
`docs/superpowers/specs/2026-08-20-nool-benchmark-suite-design.md`. It is
**pilot material, not evidence**: runs were manual, unreproducible, N=1, with
no captured prompts, models, or success criteria. It is retained verbatim for
audit; nothing here supports any quantitative claim.

Nested `.git`/`.nool` directories were renamed to `dot_git.bak`/`dot_nool.bak`
so this content could be committed inside the root repository without embedded
repos. Rust `target/` build dirs are gitignored (regenerable).

| Item | What it was | Why it is not evidence |
|---|---|---|
| `bench_{git,nool}_{single,multi}/` | Manual Claude Code runs of a Redux-in-Go task (the original 2×2) | No prompts/transcripts/metrics captured; single manual run per cell |
| `phase2_{git,nool}_{single,multi}/` | Same 2×2 with a Rust reactivity task via Antigravity | Metrics referenced machine-local conversation IDs; unreproducible |
| `parse_metrics.py` | Token/step aggregator for phase2 | Hardcoded machine paths; tokens estimated as chars/4 |
| `run_ag_evals.sh` | Antigravity transcript comparator | Printed a hardcoded conclusion regardless of data — retained as an anti-pattern example |
| `run_swarm_benchmark.sh` + `swarm_bench_results.json` + `swarm_bench_work/` | Scripted git-vs-nool merge bench | Superseded by `micro/b5_swarm_merge.py` (1-second timing, missing AST-merge scenario, cross-layer abort). Pilot result: nool ≡ git on contended scenario |
| `run_empirical_merge_test.sh` + `phase5_empirical/` | Git merge-conflict demo | No nool arm; a demonstration, not a comparison |
| `run_rogue_test.sh` + `phase3_rogue/` | Nool rejects a syntax error | No git control arm, no assertions; superseded by `micro/b4_guardrails.py` |
| `redux_test.go`, `reactivity_test.rs`, `Cargo.toml` | Loose task/test material | Recycled into `tasks/` as starter/hidden-test material |
| `phase8_*`, `phase9_*`, `test_nool_*` | Ad-hoc nool feature probes (merge, imports, governance, concurrency, invariants, workspaces) | Exploratory; no controls, no measurements |
