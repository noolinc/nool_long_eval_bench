"""B4 — Guardrails: governance-mode semantics (H4).

Tests three governance paths in both arms:
  1. DEFAULT GOVERNED PATH:   `nool propose --solidify` (full semantic validation)
  2. EXPLICIT RELAXED PATH:   `nool propose --fast --solidify` (syntax-only, deferred validation)
  3. AUTHORITY/CONTROL:       Can organizations restrict who invokes the relaxed path?

Cases, each tested against each governance path:
  syntax_broken : Go file with a parse error (hallucinated edit)
  test_breaking : parseable change that inverts behavior (tests would fail)
  clean         : positive control — a valid change (all paths must accept)

git arm (control): `git add && git commit` — records acceptance (expected: all three accepted).
nool arm: tests each governance path separately, records WHERE stopped:
          propose/solidify/deferred-validate/accepted.

Numbers and stage labels only; no interpretation.
"""

from common import TempRoot, emit, git_commit_all, make_workspace, nool_land, run

BASE = "package lib\n\nfunc Value() int { return 42 }\n"
CASES = {
    "clean": "package lib\n\nfunc Value() int { return 42 }\n\nfunc Extra() int { return 1 }\n",
    "syntax_broken": "package lib\n\nfunc Value() int { return 42 // missing close\n",
    "test_breaking": "package lib\n\nfunc Value() int { return 0 }\n",
}


def git_arm(root, case, content):
    ws = make_workspace(root, f"git_{case}")
    (ws / "lib.go").write_text(BASE)
    git_commit_all(ws, "base")
    (ws / "lib.go").write_text(content)
    code, out, _ = git_commit_all(ws, f"apply {case}")
    return {"accepted": code == 0, "exit_code": code,
            "output_tail": out.strip().splitlines()[-2:]}


def nool_arm_governed(root, case, content):
    """Default governed path: full semantic validation (project-level tests)."""
    ws = make_workspace(root, f"nool_{case}_governed", nool=True)
    (ws / "lib.go").write_text(BASE)
    (ws / "lib_test.go").write_text(
        'package lib\n\nimport "testing"\n\nfunc TestValue(t *testing.T) {\n'
        '    if Value() != 42 {\n'
        '        t.Errorf("Value() = %d, want 42", Value())\n'
        '    }\n}\n'
    )
    (ws / "go.mod").write_text("module test\n\ngo 1.21\n")
    code, out, _ = nool_land(ws, "base")
    if code != 0:
        raise RuntimeError(f"baseline land failed:\n{out}")
    (ws / "lib.go").write_text(content)

    p_code, p_out, _ = nool_land(ws, f"apply {case} (governed)")
    # No deferred validate needed — full mode validates at propose
    if p_code != 0:
        stage = "rejected_at_propose_or_solidify"
    else:
        stage = "accepted"
    return {
        "stage": stage,
        "propose_exit": p_code,
        "validate_exit": 0,
        "propose_tail": p_out.strip().splitlines()[-3:],
        "validate_tail": [],
    }


def nool_arm_fast(root, case, content):
    """Explicit relaxed path: --fast mode (syntax-only, deferred validation)."""
    ws = make_workspace(root, f"nool_{case}_fast", nool=True)
    (ws / "lib.go").write_text(BASE)
    (ws / "lib_test.go").write_text(
        'package lib\n\nimport "testing"\n\nfunc TestValue(t *testing.T) {\n'
        '    if Value() != 42 {\n'
        '        t.Errorf("Value() = %d, want 42", Value())\n'
        '    }\n}\n'
    )
    (ws / "go.mod").write_text("module test\n\ngo 1.21\n")
    code, out, _ = nool_land(ws, "base")
    if code != 0:
        raise RuntimeError(f"baseline land failed:\n{out}")
    (ws / "lib.go").write_text(content)

    p_code, p_out, _ = nool_land(ws, f"apply {case} (fast)", fast=True)
    v_code, v_out, _ = run(["nool", "validate", "--all", "--compact"], ws)

    if p_code != 0:
        stage = "rejected_at_propose_or_solidify"
    elif v_code != 0:
        stage = "flagged_by_deferred_validation"
    else:
        stage = "accepted"
    return {
        "stage": stage,
        "propose_exit": p_code,
        "validate_exit": v_code,
        "propose_tail": p_out.strip().splitlines()[-3:],
        "validate_tail": v_out.strip().splitlines()[-3:],
    }


def main():
    results = {}
    with TempRoot("b4") as root:
        for case, content in CASES.items():
            results[case] = {
                "git": git_arm(root, case, content),
                "nool_governed": nool_arm_governed(root, case, content),
                "nool_fast": nool_arm_fast(root, case, content),
            }
            print(f"[b4] {case} done")
    emit("b4_guardrails", {"cases": results})


if __name__ == "__main__":
    main()
