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
