"""B3 — Recovery from a bad landing (H4/operational).

Timeline built identically in both arms:
  L1 good (a.go)  L2 good (b.go)  L3 BAD (breaks b.go)  L4 good unrelated (d.go)

Recovery goal: remove L3's damage while keeping L4's unrelated work.
  git arm : `git revert --no-edit <L3>`
  nool arm: land L3 on its own thread, then `nool pluck <thread> --execute`
            + land the restored state (the documented selective-undo path).

Metrics: wall time, command count, success (b.go restored), collateral
(d.go survives), history preserved (no rewrite).
"""

import time

from common import TempRoot, emit, git_commit_all, make_workspace, nool_land, run

REPS = 5

GOOD_B = "package lib\n\nfunc Working() int { return 2 }\n"
BAD_B = "package lib\n\nfunc Working() int { return 0 } // sabotaged\n"
GOOD_D = "package lib\n\nfunc Unrelated() int { return 4 }\n"


def build_timeline(ws, arm, l4_thread=None):
    (ws / "a.go").write_text("package lib\n\nfunc A() int { return 1 }\n")
    land(ws, arm, "L1 add a.go")
    (ws / "b.go").write_text(GOOD_B)
    land(ws, arm, "L2 add b.go")
    (ws / "b.go").write_text(BAD_B)
    land(ws, arm, "L3 sabotage b.go", thread="badwork")
    bad_ref = head(ws, arm)
    (ws / "d.go").write_text(GOOD_D)
    land(ws, arm, "L4 unrelated d.go", thread=l4_thread)
    return bad_ref


def land(ws, arm, msg, thread=None):
    if arm == "git":
        code, out, _ = git_commit_all(ws, msg)
    else:
        extra = ["--thread", thread] if thread else None
        code, out, _ = nool_land(ws, msg, extra=extra)
    if code != 0:
        raise RuntimeError(f"land failed [{arm}] {msg}:\n{out}")


def head(ws, arm):
    code, out, _ = run(["git", "rev-parse", "HEAD"], ws, check=True)
    return out.strip()


def recover(ws, arm, bad_ref):
    cmds = []
    t0 = time.monotonic()
    if arm == "git":
        code, out, _ = run(["git", "revert", "--no-edit", bad_ref], ws)
        cmds.append(("git revert", code))
    else:
        code, out, _ = run(["nool", "pluck", "badwork", "--execute", "--compact"], ws)
        cmds.append(("nool pluck badwork --execute", code))
        if code == 0:
            code2, out2, _ = run(["nool", "propose", "--all", "--intent",
                                  "land post-pluck state", "--fast", "--solidify",
                                  "--compact"], ws)
            cmds.append(("nool propose post-pluck", code2))
            out += out2
    ms = (time.monotonic() - t0) * 1000.0
    return cmds, ms, out


VARIANTS = {
    # L4 lands on the default thread — a linear timeline, the way an agent
    # loop that never sets threads would leave history.
    "linear_timeline": None,
    # L4 lands on its own thread — nool's commutative-threads discipline.
    "threaded_timeline": "otherwork",
}


def main():
    reps = {}
    with TempRoot("b3") as root:
        for variant, l4_thread in VARIANTS.items():
            arms = {"git": [], "nool": []}
            reps[variant] = arms
            for arm in ("git", "nool"):
                if arm == "git" and variant == "threaded_timeline":
                    continue  # git has no thread concept; linear covers it
                for rep in range(REPS):
                    ws = make_workspace(root, f"{variant}_{arm}_{rep}",
                                        nool=(arm == "nool"))
                    bad_ref = build_timeline(ws, arm, l4_thread)
                    cmds, ms, out = recover(ws, arm, bad_ref)
                    b_now = (ws / "b.go").read_text() if (ws / "b.go").exists() else ""
                    d_now = (ws / "d.go").read_text() if (ws / "d.go").exists() else ""
                    arms[arm].append({
                        "recovery_ms": round(ms, 1),
                        "commands": [c for c, _ in cmds],
                        "command_count": len(cmds),
                        "all_commands_succeeded": all(code == 0 for _, code in cmds),
                        "damage_removed": b_now == GOOD_B,
                        "unrelated_work_survived": d_now == GOOD_D,
                        "output_tail": out.strip().splitlines()[-3:],
                    })
                    print(f"[b3] {variant} {arm} rep {rep} done")
    emit("b3_recovery", {"config": {"reps": REPS}, "variants": reps})


if __name__ == "__main__":
    main()
