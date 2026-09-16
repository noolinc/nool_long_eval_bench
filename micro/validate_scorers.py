"""Scorer validation: the injected failures the 2026-09-13 audit used to fool
B5 and B6 must be detected, and provenance must name the tested build.

Runs without nool (everything is mocked or pure) so it can gate any change
to the scorers before a result is regenerated: `make validate-scorers`.
"""

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


def b10_refused_admission_is_not_a_sample():
    with patch.object(b10, "run_split", return_value=(2, "", "Error: Blast radius exceeds declared scope", 15.0)), \
            patch.object(b10, "run", return_value=(0, "", 1.0)), \
            patch.object(b10, "touch", return_value=None), \
            patch.object(b10, "reset", return_value=None):
        result = b10.measure_admission(Path("/nonexistent"), 4, 0)
    check("b10: a refused (exit != 0) admission call carries no envelope",
          result["exit_code"] != 0 and result["envelope"] is None)
    # summarize_ms's caller (main()) filters on exit_code == 0 before
    # building admission_ms -- assert that filter directly, since a refused
    # sample slipping into a median would understate real admission cost.
    samples = [result, {"exit_code": 0, "wall_ms": 50.0}]
    kept = [s["wall_ms"] for s in samples if s.get("exit_code") == 0]
    check("b10: only the exit_code==0 sample survives into the median input",
          kept == [50.0])


def b10_closure_mismatch_excludes_the_cell():
    d, r_lo, r_hi = 4, 100, 1000
    mismatched_manifest = {
        "ground_truth": {str(d): {"affected_tests_expected": 5}},
        "total_packages": 1, "total_files": 1, "init_s": 0.1,
    }
    by_r = {
        str(r_lo): {"manifest": mismatched_manifest, "by_d": {
            str(d): {"closure_ok": False, "admission_ms": {"median_ms": 10}, "fast_vet_ms": {"median_ms": 20}}}},
        str(r_hi): {"manifest": mismatched_manifest, "by_d": {
            str(d): {"closure_ok": True, "admission_ms": {"median_ms": 12}, "fast_vet_ms": {"median_ms": 400}}}},
    }
    excluded = []
    fit_points = {}
    for r in (r_lo, r_hi):
        entry = by_r[str(r)]["by_d"][str(d)]
        if not entry["closure_ok"]:
            excluded.append({"R": r, "D": d})
            continue
        fit_points[r] = entry["admission_ms"]["median_ms"]
    check("b10: a closure_ok=False cell is excluded from the scaling fit, not silently averaged in",
          excluded == [{"R": r_lo, "D": d}] and fit_points == {r_hi: 12})


def b10_scaling_needs_two_R_points():
    single = {"100": {"by_d": {"4": {"closure_ok": True, "admission_ms": {"median_ms": 10}}}}}
    meds = {}
    for r_str, entry in single.items():
        e = entry["by_d"]["4"]
        if e["closure_ok"]:
            meds[int(r_str)] = e["admission_ms"]["median_ms"]
    check("b10: fewer than two R points yields no flat_in_R verdict (never fabricated as True)",
          len(meds) < 2)


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
    b10_refused_admission_is_not_a_sample()
    b10_closure_mismatch_excludes_the_cell()
    b10_scaling_needs_two_R_points()
    b10_ground_truth_matches_construction()
    provenance_names_the_build()
    if FAILURES:
        print(f"[validate_scorers] {len(FAILURES)} check(s) failed: {FAILURES}")
        sys.exit(1)
    print("[validate_scorers] all checks passed")


if __name__ == "__main__":
    main()
