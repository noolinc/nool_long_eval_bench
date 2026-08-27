#!/usr/bin/env python3
"""Corpus v3.1: subset-parametrized reference implementations.

Composes the per-cluster generators (refs_v31_<cluster>.emit(ws, enabled))
into apply_enabled(ws, enabled): a workspace implementing EXACTLY the given
ticket subset, with every disabled ticket at starter semantics. Emission
order matches refs.apply_all (billing, users, orders, store, api, ids,
clock, fillers); with the full ticket set the output must be byte-identical
to refs.apply_all — validate_loo.py check 1 enforces that fidelity oracle.

The clock cluster (t19) and the filler tickets (t41-t60, one file each,
identified by the "(tNN)" marker comment in refs.FILLER_FILES) are
decomposed inline here; the six multi-ticket clusters live in their own
refs_v31_* modules.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refs  # noqa: E402
import refs_v31_billing as billing  # noqa: E402
import refs_v31_users as users  # noqa: E402
import refs_v31_orders as orders  # noqa: E402
import refs_v31_store as store  # noqa: E402
import refs_v31_api as api  # noqa: E402
import refs_v31_ids as ids  # noqa: E402

CLUSTERS = [("billing", billing), ("users", users), ("orders", orders),
            ("store", store), ("api", api), ("ids", ids)]

CLOCK_TICKET = "t19"

FILLER_TICKET_FILE = {}
for _rel, _content in refs.FILLER_FILES.items():
    _tids = sorted(set(re.findall(r"\((t\d+)\)", _content)))
    assert len(_tids) == 1, f"filler file {_rel} names tickets {_tids}"
    FILLER_TICKET_FILE[_tids[0]] = _rel

ALL = sorted(
    set().union(*[set(m.TICKETS) for _, m in CLUSTERS])
    | {CLOCK_TICKET} | set(FILLER_TICKET_FILE),
    key=lambda t: int(t[1:]))


def apply_enabled(ws, enabled):
    enabled = set(enabled)
    unknown = enabled - set(ALL)
    assert not unknown, f"unknown tickets: {sorted(unknown)}"
    for _name, mod in CLUSTERS:
        mod.emit(ws, enabled & set(mod.TICKETS))
    if CLOCK_TICKET in enabled:
        refs.apply_clock(ws)
    for tid, rel in FILLER_TICKET_FILE.items():
        if tid in enabled:
            refs.W(ws, rel, refs.FILLER_FILES[rel])
    # The starter smoke test pins Invoice(1000); its expectation tracks
    # whichever billing tickets are enabled (refs.apply_all hardcodes the
    # full-set value 1127 — invoice_1000 generalizes that to any subset).
    v = billing.invoice_1000(enabled & set(billing.TICKETS))
    if v != 1100:
        p = os.path.join(ws, "smoke_test.go")
        src = open(p).read().replace("!= 1100", f"!= {v}") \
                           .replace("want 1100", f"want {v}")
        refs.W(ws, "smoke_test.go", src)


def cluster_of(tid):
    for name, mod in CLUSTERS:
        if tid in mod.TICKETS:
            return name, list(mod.TICKETS)
    if tid == CLOCK_TICKET:
        return "clock", [CLOCK_TICKET]
    if tid in FILLER_TICKET_FILE:
        return "fillers", sorted(FILLER_TICKET_FILE,
                                 key=lambda t: int(t[1:]))
    raise KeyError(tid)
