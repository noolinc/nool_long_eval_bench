"""Scorer validation: the injected failures the 2026-09-13 audit used to fool
B5 and B6 must be detected, and provenance must name the tested build.

Runs without nool (everything is mocked or pure) so it can gate any change
to the scorers before a result is regenerated: `make validate-scorers`.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import b5_swarm_merge as b5  # noqa: E402
import b6_context_retrieval as b6  # noqa: E402
import b10_assurance_scaling as b10  # noqa: E402
import common  # noqa: E402

FAILURES = []


def check(name, condition, detail=""):
    print(f"  [{'ok' if condition else 'FAIL'}] {name}{(' - ' + detail) if detail and not condition else ''}")
    if not condition:
        FAILURES.append(name)


def b5_refused_merges_are_not_successes():
    with patch.object(b5, "run", return_value=(1, "fatal: simulated refusal", 1)), \
            patch.object(b5, "tree_conflicted", return_value=False):
        branches, _, _ = b5.merge_all(Path("/nonexistent"), "nool", "diff_functions")
    check("b5: a refused merge (exit 1, clean tree) is not a success",
          sum(b["success"] for b in branches) == 0,
          f"{sum(b['success'] for b in branches)} counted")
    check("b5: tree_clean still records the file-level view",
          all(b["tree_clean"] for b in branches))


def b5_silent_noops_are_not_successes():
    with patch.object(b5, "run", return_value=(0, "", 1)), \
            patch.object(b5, "tree_conflicted", return_value=False):
        branches, _, _ = b5.merge_all(Path("/nonexistent"), "git", "same_anchor")
    check("b5: exit 0 with nothing landed is a silent no-op, not a success",
          sum(b["success"] for b in branches) == 0
          and sum(b["silent_noop"] for b in branches) == len(branches))


def b5_partial_landing_is_not_a_success(tmp):
    ws = tmp / "b5partial"
    ws.mkdir()
    (ws / "server.go").write_text("package server\n\nfunc (s *Server) Agent1Method() {}\n")
    heads = iter(["a", "b"] * 40)

    def fake_run(cmd, cwd, **kw):
        if cmd[:2] == ["git", "rev-parse"]:
            return 0, next(heads), 1
        return 0, "", 1
    with patch.object(b5, "run", side_effect=fake_run), \
            patch.object(b5, "tree_conflicted", return_value=False):
        branches, _, _ = b5.merge_all(ws, "git", "diff_functions")
    check("b5: only the branch whose change is present counts",
          [b["success"] for b in branches] == [True] + [False] * (len(branches) - 1))


def b6_heading_echo_is_not_a_hit():
    heading_only = "Context for: ratelimit.go#ApplyRateLimit\n" + "=" * 40 + "\n"
    scored = b6.score_context(heading_only, "ApplyRateLimit")
    check("b6: a heading echoing the query is not a hit",
          not scored["hit"] and scored["heading_only"])
    with_record = heading_only + \
        "Entity: ApplyRateLimit [ast_node] (entity:ApplyRateLimit:0123456789abcdef)\n"
    scored = b6.score_context(with_record, "ApplyRateLimit")
    check("b6: an entity record naming the function is a hit",
          scored["hit"] and len(scored["records"]) == 1)
    other = heading_only + "Entity: ratelimit.go [file] (entity:ratelimit.go:0123456789abcdef)\n"
    check("b6: a record for a different entity is not a hit",
          not b6.score_context(other, "ApplyRateLimit")["hit"])
    unresolved = "Context for: x#Nope\n  [Unresolved] 'x#Nope' matches no entity or feature\n"
    scored = b6.score_context(unresolved, "Nope")
    check("b6: an unresolved answer is flagged and never a hit",
          scored["unresolved"] and not scored["hit"])


def b6_search_derives_next_step_from_output():
    out = "Query: semantic search(\"rate limiting\")\n" + "-" * 40 + "\n" \
          "  \U0001F4CA 1a2b3c4d | implement rate limiting for client request budgets | thread: main\n"
    scored = b6.score_search(out, "rate limiting for client request budgets")
    check("b6: search hit is the intent among returned references, first knot derived",
          scored["hit"] and scored["first_knot"] == "1a2b3c4d")
    check("b6: an empty search derives nothing and misses",
          b6.score_search("Query: semantic search(\"x\")\n  No results found.\n", "y")
          == {"refs": [], "hit": False, "first_knot": None})
    check("b6: a missing knot is a miss, not an error",
          b6.measure_materialize(Path("/nonexistent"), None, "func X(")["hit"] is False)


def provenance_names_the_build():
    prov = common.provenance()
    check("provenance: immutable run id", len(prov.get("run_id", "")) == 36)
    sha = prov.get("binary_sha256", "")
    check("provenance: binary sha256 or an explicit unavailability",
          len(sha) == 64 or sha.startswith("unavailable"))
    build = prov.get("nool_build", {})
    check("provenance: the build reports its source sha and dirtiness, or says it cannot",
          ("git_sha" in build and "dirty" in build) or "unavailable" in build)
    check("provenance: harness revision recorded", "git_sha" in prov.get("harness", {}))
    check("provenance: daemon mode explicit", "NOOL_NO_DAEMON" in prov.get("daemon_mode", ""))


def _b10_patched(run_split_result=None, run_split_exc=None):
    rs = patch.object(b10, "run_split", side_effect=run_split_exc) if run_split_exc \
        else patch.object(b10, "run_split", return_value=run_split_result)
    return (rs, patch.object(b10, "run", return_value=(0, "", 1.0)),
            patch.object(b10, "touch", return_value=None),
            patch.object(b10, "reset", return_value=None))


SIGNAL = '{"semantic_signal": {"blast_radius": {"affected": 10, "status": "known"}, ' \
         '"envelope": {"contracts": []}, "evidence_plan": {"plan": "PackageTests"}}}\n'


def b10_refused_propose_is_not_a_landing():
    # A refused propose that still printed a full semantic_signal.
    rs, r, t, rst = _b10_patched((2, SIGNAL, "Error: Blast radius exceeds declared scope", 15.0))
    with rs, r, t, rst:
        result = b10.measure_admission(Path("/nonexistent"), 4, 0)
    check("b10: exit 2 with a semantic_signal on stdout is refused, not landed",
          result["outcome"] == "refused")
    check("b10: exit 3 (coordination conflict) is refused",
          b10.classify_outcome(3, SIGNAL, False) == "refused")
    check("b10: exit 0 without a semantic_signal is no_signal, not landed",
          b10.classify_outcome(0, "ok\n", False) == "no_signal")
    landed = {"outcome": "landed", "wall_ms": 50.0}
    t_ = b10.timing([result, landed])
    check("b10: only the landed sample enters summarize_ms",
          t_ is not None and t_["n"] == 1 and t_["median_ms"] == 50.0)
    counts = b10.outcome_counts([result, landed])
    check("b10: landed/refused counts reflect the classification",
          counts["landed"] == 1 and counts["refused"] == 1)


def b10_timeout_is_not_a_sample():
    exc = subprocess.TimeoutExpired(cmd="nool propose", timeout=1)
    rs, r, t, rst = _b10_patched(run_split_exc=exc)
    with rs, r, t, rst:
        result = b10.measure_admission(Path("/nonexistent"), 4, 0)
    check("b10: a timed-out propose is dnf with no wall time",
          result["outcome"] == "dnf" and result["wall_ms"] is None)
    check("b10: a dnf never becomes a timing sample",
          b10.timing([result]) is None and b10.outcome_counts([result])["dnf"] == 1)
    check("b10: a timeout that somehow carries a wall time is still excluded",
          b10.timing([{"outcome": "dnf", "wall_ms": 120000.0}]) is None)


def b10_empty_selection_is_not_o_change():
    check("b10: an empty selected list is `empty`, not an O(change) selection",
          b10.classify_selection({"mode": "selected", "tests": []}, 5) == "empty")
    check("b10: a full-suite fallback (tests: [] + run_all) is `full_fallback`, not exact",
          b10.classify_selection({"mode": "full", "run_all": True, "tests": []}, 5) == "full_fallback")
    check("b10: a selection of the wrong size is a mismatch",
          b10.classify_selection({"mode": "selected", "tests": [{}] * 3}, 5) == "mismatch")
    check("b10: only the constructed-size selection is exact",
          b10.classify_selection({"mode": "selected", "tests": [{}] * 5}, 5) == "exact")
    manifest = {"ground_truth": {"4": {"envelope_expected": 10}}}
    adm = [{"outcome": "landed", "envelope": 10}]
    check("b10: an empty selection fails the closure check (excluded from the fit)",
          b10.closure_check(manifest, 4, "empty", adm)["ok"] is False)
    check("b10: a refused admission's envelope never satisfies the closure check",
          b10.closure_check(manifest, 4, "exact",
                            [{"outcome": "refused", "envelope": 10}])["ok"] is False)


def b10_stale_binary_is_rejected():
    good = {"path": "/bench/work/bin/nool", "sha256": "a" * 64,
            "build": {"version": "7.9.2", "git_sha": "f" * 40, "dirty": False}}
    check("b10: an unchanged, clean, frozen binary passes the gate",
          b10.binary_gate(good, good)["valid"])
    swapped = {**good, "sha256": "b" * 64}
    check("b10: a binary replaced mid-run invalidates the result",
          "binary_changed_during_run" in b10.binary_gate(good, swapped)["reasons"])
    dirty = {**good, "build": {**good["build"], "dirty": True}}
    check("b10: a dirty-tree build is rejected",
          not b10.binary_gate(dirty, dirty)["valid"])
    unknown = {**good, "build": {"unavailable": "x"}}
    check("b10: a build that cannot report dirtiness is rejected",
          not b10.binary_gate(unknown, unknown)["valid"])
    tgt = {**good, "path": "/src/Nool/target/debug/nool"}
    check("b10: a mutable cargo target/ binary is rejected",
          "mutable_cargo_target_binary" in b10.binary_gate(tgt, tgt)["reasons"])


def b10_var_folders_temp_root_is_rejected():
    for bad in ("/var/folders/x1/abc/T/noolbench_b10", "/private/var/folders/x1/abc/T/nb"):
        try:
            b10.check_temp_root(bad)
            ok = False
        except ValueError:
            ok = True
        check(f"b10: temp root {bad.split('/T/')[0]}/... is refused", ok)
    import tempfile
    sys_tmp = tempfile.gettempdir()
    if sys_tmp.startswith(("/var/folders", "/private/var/folders")):
        try:
            b10.check_temp_root(sys_tmp)
            ok = False
        except ValueError:
            ok = True
        check("b10: this machine's default tempfile dir is refused", ok)
    try:
        b10.check_temp_root("/tmp/noolbench_b10")
        ok = True
    except ValueError:
        ok = False
    check("b10: the pinned /tmp root is accepted", ok)


def b10_scoring_excludes_mismatch_keeps_fallback():
    def cell(ok, reason, adm, env):
        return {"closure": {"ok": ok, "reason": reason}, "admission_ms": {"median_ms": adm},
                "affected_tests_ms": {"median_ms": 5}, "full_propose_ms": {"median_ms": 100},
                "git_control": {"vet_ms": {"median_ms": 50}}, "envelope_observed": env,
                "selection_class": "exact" if ok else "mismatch"}
    by_r = {
        "100": {"by_d": {"0": cell(True, None, 100, 2), "4": cell(False, "selection_empty", 1, 10)}},
        "1000": {"by_d": {"0": cell(True, None, 150, 2), "4": cell(True, None, 400, 10)}},
    }
    sc = b10.score(by_r)
    check("b10: a failed closure cell is excluded from the scaling fit and listed",
          sc["excluded"] == [{"R": 100, "D": 4, "reason": "selection_empty"}]
          and list(sc["by_d"]["4"]["medians_by_R"]) == [1000])
    check("b10: fewer than two R points yields no flat_in_R verdict (never fabricated as True)",
          sc["by_d"]["4"]["admission_flat_in_R"] is None and sc["H1_flat_in_R_all_D"] is None)
    check("b10: the pre-registered ratio is hi/lo admission median, <= 2 is flat",
          sc["by_d"]["0"]["admission_ratio_hi_over_lo"] == 1.5 and sc["by_d"]["0"]["admission_flat_in_R"])


def b10_ground_truth_matches_construction():
    from b10_fixture import generate as gen
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        m = gen(Path(tmp), 30, d_levels=(0, 4))
    gt = m["ground_truth"]
    check("b10 fixture: D=0 target has a 1-file closure (envelope 2) by construction",
          gt["0"]["closure_files_expected"] == 1 and gt["0"]["envelope_expected"] == 2)
    check("b10 fixture: D=4 target has a 9-file closure (envelope 10), affected_tests=5",
          gt["4"]["closure_files_expected"] == 9 and gt["4"]["envelope_expected"] == 10
          and gt["4"]["affected_tests_expected"] == 5)
    check("b10 fixture: filler count is R minus the reserved target/leaf packages",
          m["n_fillers"] == 30 - (1 + 0) - (1 + 4))


def main():
    import tempfile
    print("[validate_scorers] injected-failure checks")
    b5_refused_merges_are_not_successes()
    b5_silent_noops_are_not_successes()
    with tempfile.TemporaryDirectory() as tmp:
        b5_partial_landing_is_not_a_success(Path(tmp))
    b6_heading_echo_is_not_a_hit()
    b6_search_derives_next_step_from_output()
    b10_refused_propose_is_not_a_landing()
    b10_timeout_is_not_a_sample()
    b10_empty_selection_is_not_o_change()
    b10_stale_binary_is_rejected()
    b10_var_folders_temp_root_is_rejected()
    b10_scoring_excludes_mismatch_keeps_fallback()
    b10_ground_truth_matches_construction()
    provenance_names_the_build()
    if FAILURES:
        print(f"[validate_scorers] {len(FAILURES)} check(s) failed: {FAILURES}")
        sys.exit(1)
    print("[validate_scorers] all checks passed")


if __name__ == "__main__":
    main()
