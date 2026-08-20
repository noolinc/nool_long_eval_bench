"""B7 — Regression localization: `nool debug bisect` vs `git bisect run`.

A repo is built as K sequential landings; landing BAD_INDEX silently breaks
behavior a committed test asserts. Both arms then localize the culprit with
their native binary-search tool and the same test command.

Metrics: culprit correctly identified, wall ms, and (where reported) steps.
Ground truth is known by construction.
"""

import re
import time

from common import TempRoot, emit, git_commit_all, make_workspace, nool_land, run

K = 12
BAD_INDEX = 7  # 1-based landing number that introduces the regression

TEST_GO = """package lib

import "testing"

func TestValue(t *testing.T) {
\tif Value() != 42 {
\t\tt.Fatalf("Value() = %d, want 42", Value())
\t}
}
"""


def lib_source(upto, broken_at=None):
    lines = ["package lib\n"]
    v = "42" if (broken_at is None or upto < broken_at) else "41"
    lines.append(f"\nfunc Value() int {{ return {v} }}\n")
    for i in range(1, upto + 1):
        lines.append(f"\nfunc Extra{i}() int {{ return {i} }}\n")
    return "".join(lines)


def build(ws, arm):
    (ws / "lib.go").write_text(lib_source(0))
    (ws / "lib_test.go").write_text(TEST_GO)
    (ws / "go.mod").write_text("module bench/lib\n\ngo 1.24\n")
    land(ws, arm, "landing 0: base with test")
    ids = []
    for i in range(1, K + 1):
        (ws / "lib.go").write_text(lib_source(i, broken_at=BAD_INDEX))
        land(ws, arm, f"landing {i}: add Extra{i}")
        ids.append(head_git(ws))
    return ids


def land(ws, arm, msg):
    if arm == "git":
        code, out, _ = git_commit_all(ws, msg)
    else:
        code, out, _ = nool_land(ws, msg)
    if code != 0:
        raise RuntimeError(f"land failed: {msg}\n{out}")


def head_git(ws):
    _, out, _ = run(["git", "rev-parse", "HEAD"], ws, check=True)
    return out.strip()


def git_arm(root):
    ws = make_workspace(root, "git")
    shas = build(ws, "git")
    good_sha = head_first = None
    _, log, _ = run(["git", "log", "--reverse", "--format=%H %s"], ws, check=True)
    first_line = log.splitlines()[0]
    good_sha = first_line.split()[0]
    truth_sha = shas[BAD_INDEX - 1]
    t0 = time.monotonic()
    run(["git", "bisect", "start", "HEAD", good_sha], ws)
    code, out, _ = run(["git", "bisect", "run", "go", "test", "./..."], ws,
                       timeout=600)
    ms = (time.monotonic() - t0) * 1000.0
    m = re.search(r"([0-9a-f]{40}) is the first bad commit", out)
    found = m.group(1) if m else None
    run(["git", "bisect", "reset"], ws)
    steps = len(re.findall(r"Bisecting:", out))
    return {"culprit_found": found == truth_sha, "wall_ms": round(ms, 1),
            "bisect_steps": steps, "exit_code": code}


def nool_arm(root):
    ws = make_workspace(root, "nool", nool=True)
    build(ws, "nool")
    code, out, _ = run(["nool", "log", "--json"], ws)
    import json as _json
    knots = _json.loads(out)
    # nool log is newest-first; map to landing order oldest-first.
    knots_old_first = list(reversed(knots))
    good_id = next(k["id"] for k in knots_old_first if "landing 0" in k["intent"])
    truth_id = next(k["id"] for k in knots_old_first
                    if f"landing {BAD_INDEX}:" in k["intent"])
    bad_id = next(k["id"] for k in knots_old_first
                  if f"landing {K}:" in k["intent"])
    # --bad must be explicit: the HEAD default resolves outside knot-id space
    # in nool 6.13 and reports "No knots found between good and bad".
    t0 = time.monotonic()
    code, out, _ = run(["nool", "debug", "bisect", "--good", good_id,
                        "--bad", bad_id,
                        "--test", "go test ./...", "--compact"], ws, timeout=600)
    ms = (time.monotonic() - t0) * 1000.0
    found = truth_id[:8] in out or truth_id in out
    steps = len(re.findall(r"(?i)testing knot|step ", out))
    m = re.search(r"First bad Knot: ([0-9a-f]+)", out)
    named = m.group(1) if m else None
    named_intent = next((k["intent"] for k in knots_old_first
                         if named and k["id"].startswith(named)), None)
    return {"culprit_found": found, "wall_ms": round(ms, 1),
            "bisect_steps_reported": steps, "exit_code": code,
            "knot_named": named, "knot_named_intent": named_intent,
            "truth_intent": f"landing {BAD_INDEX}",
            "output_tail": out.strip().splitlines()[-4:]}


def main():
    with TempRoot("b7") as root:
        results = {"git": git_arm(root), "nool": nool_arm(root)}
    emit("b7_regression_localization", {
        "config": {"landings": K, "bad_landing": BAD_INDEX},
        "arms": results,
    })


if __name__ == "__main__":
    main()
