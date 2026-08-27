# Corpus v3 validation harness

`tickets_v3.json` and `accept/t21..t60` are the committed corpus artifacts;
`build_v3.py` + `fillers.py` + `emit.py` are their authoring provenance.

`validate.py` proves the property the two t2 artifacts violated: every
acceptance test passes against combined reference implementations of its
own cluster alone, and against all 60 tickets implemented simultaneously
(plus the smoke suite). `refs.py` holds those reference implementations.

Run after any corpus or accept-test change:

    python3 tasks/fleet_service/validation_v3/emit.py     # only if regenerating
    python3 tasks/fleet_service/validation_v3/validate.py

Exit 0 with `TOTAL FAILURES: 0` is the bar for landing corpus changes.

Corpus v3.1 additionally proves that a test cannot be satisfied by a
cluster-mate's landed implementation: `validate_loo.py` generates the full
within-cluster leave-one-out matrix using `refs_v31*.py`. It also mutation
tests comparison guards on each ticket's attributed code:

    python3 tasks/fleet_service/validation_v3/validate_loo.py
    python3 tasks/fleet_service/validation_v3/validate_mutation.py

Both commands must exit 0. Their JSON reports are written under
`results/micro/`; they are validation evidence, not fleet-run outcomes.

The mutation bar excludes hand-verified equivalent mutants (clamp/min/max
boundary flips that are semantic no-ops) via an in-file allowlist with
per-entry justifications; stale allowlist entries after a refs change fail
the run. The first full run (2026-08-27) surfaced three genuine boundary
weaknesses — t4 (expiry at exactly `expiresAt`), t36 (leading-`@` display
name), t54 (leading-`@` email domain) — fixed by strengthening those
acceptance tests in corpus v3.1.
