"""B4 — Guardrails with a control arm (H4).

Cases, each landed identically in both arms:
  syntax_broken : Go file with a parse error (a classic hallucinated edit)
  test_breaking : parseable change that inverts behavior (tests would fail)
  clean         : positive control — a valid change (both arms must accept)

git arm : `git add && git commit` — records whether git accepts (expected: yes).
nool arm: `nool propose --fast --solidify`, then `nool validate --all` —
          records WHERE (if anywhere) the change is stopped:
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


def nool_arm(root, case, content):
    ws = make_workspace(root, f"nool_{case}", nool=True)
    (ws / "lib.go").write_text(BASE)
    code, out, _ = nool_land(ws, "base")
    if code != 0:
        raise RuntimeError(f"baseline land failed:\n{out}")
    (ws / "lib.go").write_text(content)

    p_code, p_out, _ = nool_land(ws, f"apply {case}")
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
                "nool": nool_arm(root, case, content),
            }
            print(f"[b4] {case} done")
    emit("b4_guardrails", {"cases": results})


if __name__ == "__main__":
    main()
