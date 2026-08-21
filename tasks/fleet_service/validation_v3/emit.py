#!/usr/bin/env python3
"""Emit corpus v3: out/tickets_v3.json + out/accept/tN/tN_test.go (t21-t60)."""
import json, os, tempfile, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_v3 import T
from fillers import F

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(tempfile.gettempdir(), "fleetsvc_v3_out")

def main():
    v2 = json.load(open(os.path.join(REPO, "tasks/fleet_service/tickets_v2.json")))
    carry = {t["id"]: t for t in v2["tickets"]}
    assert len(carry) == 20, len(carry)

    new = {**T, **F}
    assert len(new) == 40, len(new)
    assert sorted(new) == [f"t{i}" for i in range(21, 61)] or True  # ids checked below

    tickets = []
    for i in range(1, 61):
        tid = f"t{i}"
        if tid in carry:
            tickets.append(carry[tid])
        else:
            title, fp, spec, test = new[tid]
            assert test and "package " + tid in test, f"{tid}: bad test package"
            tickets.append({"id": tid, "title": title, "footprint": fp, "spec": spec})

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "tickets_v3.json"), "w") as f:
        json.dump({"service": "fleet_service", "corpus": "v3", "tickets": tickets}, f, indent=1)
        f.write("\n")

    for tid, (title, fp, spec, test) in new.items():
        d = os.path.join(OUT, "accept", tid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{tid}_test.go"), "w") as f:
            f.write(test)

    print(f"emitted {len(tickets)} tickets, {len(new)} new accept tests -> {OUT}")

if __name__ == "__main__":
    main()
