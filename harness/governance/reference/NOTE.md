# Reference DSL policy packs — NOT active in the benchmark.

These files follow the documented schema (docs/policies: inv_id, scope,
kind, severity, mode, stages, forbids/requires predicates). They were
authored for the nool treatment arms and then DEMOTED to reference material
because they are empirically inert on the pinned CLI version:

  2026-08-22, nool CLI (see run provenance for exact version):
  - policies/no_secret_keys.yaml (blocking, pre-solidify): a diff
    introducing `ghp_AAAA...` (GitHub PAT) proposed with --full and
    solidified successfully; rule did not fire.
  - The docs' own canonical example (no-todo.yaml, diff_contains "TODO",
    pre-solidify) also did not block.
  - A doctor-stage rule (stages: ["doctor"]) produced no findings;
    `nool doctor` reported "No doctor-stage gate findings" while
    simultaneously suggesting that exact rule form.
  - Probe matrix later the same day (fresh projects each time): rules that
    OMIT stages entirely (guide default: every stage), blocking
    diff_contains on plaintext "TODO", with and without the [aram]
    section, with and without the daemon running, under propose --fast
    and propose --full — none enforced. Files parse (schema errors appear
    when scope/kind are missing and vanish once corrected), so loading
    succeeds but evaluation never rejects.
  - Root cause of non-load was narrowed to the [aram] section being
    present or absent makes no difference; TOML-native governance
    ([invariants], [steer], [gating]) DOES evaluate (`nool verify --all`
    reports controls satisfied/violated).

Consequence for the benchmark design:
  - Secret scanning is enforced as a SYMMETRIC harness-level gate
    (fleet_run.secret_scan) applied identically to every arm — this is
    both fair and immune to substrate defects.
  - The nool arm's governance profile contains only verified-enforcing
    TOML sections.
  - The docs-vs-behavior gap itself is reported as a governance finding.

If a future CLI version loads these packs, move them back to
policies/ next to nool_governed.toml and re-run the validation sequence
in this file's history before trusting them.
