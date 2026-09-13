"""B6 — Semantic context retrieval (the "structured context" claim).

A repo with F files x G functions is built knot-by-knot with recorded
intents; one feature ("rate limiting") has known ground-truth locations.
An agent needing that context can either:

  nool arm : `nool query search "<intent>"` and `nool query context <node>`
  baseline : what agents actually do in a git repo — grep for terms, then
             read every matching file in full.

Metrics per query: bytes the agent must ingest (stdout only), wall ms, and
hit. A hit is a returned entity RECORD naming the ground-truth function
(`Entity: <name> [<kind>] (<id>)`), never the `Context for:` heading, which
merely echoes the query: the 2026-09-13 audit found the original
`contains in out` criterion scoring a heading-only answer, and a
nonexistent symbol, as retrieval successes. A negative control
(nonexistent symbol) is scored alongside and must not hit. The chained
"search then context" flow derives its second step from the search output
itself (the surfaced knot is materialized), not from the ground truth.
Bytes are reported as bytes — no token conversion.
"""

import re
import time

from common import TempRoot, emit, make_workspace, nool_land, run, run_split

ENTITY_LINE = re.compile(r"^Entity: (\S+) \[(\w+)\] \((entity:[^)]+)\)")
SEARCH_LINE = re.compile(r"^\s*\S*\s*([0-9a-f]{8})\s*\|\s*(.*?)\s*(\||$)")
NEGATIVE_SYMBOL = "NoSuchFunctionForControl"

N_FILES = 12
FUNCS_PER_FILE = 4
GROUND_TRUTH_FILE = "ratelimit.go"
GROUND_TRUTH_FUNC = "ApplyRateLimit"

QUERIES = [
    ("intent_search", "rate limiting"),
    ("entity_context", None),  # filled with the ground-truth node id
]


def build_repo(root):
    ws = make_workspace(root, "ctx", nool=True)
    for i in range(N_FILES):
        name = f"module_{i:02d}.go"
        body = [f"package app\n"]
        for g in range(FUNCS_PER_FILE):
            body.append(
                f"\n// Helper{i:02d}x{g} does bookkeeping for subsystem {i}.\n"
                f"func Helper{i:02d}x{g}(n int) int {{ return n + {i * 10 + g} }}\n")
        (ws / name).write_text("".join(body))
        code, out, _ = nool_land(ws, f"add subsystem {i} helpers")
        if code != 0:
            raise RuntimeError(out)
    (ws / GROUND_TRUTH_FILE).write_text(
        "package app\n\n"
        "// ApplyRateLimit enforces the per-client request budget.\n"
        "func ApplyRateLimit(clientID string, budget int) bool {\n"
        "\treturn Helper00x0(budget) > 0\n"
        "}\n")
    code, out, _ = nool_land(ws, "implement rate limiting for client request budgets")
    if code != 0:
        raise RuntimeError(out)
    return ws


def score_context(stdout, wanted_symbol):
    """Entity records in a `query context` answer, and whether one of them IS
    the wanted symbol. Headings, diagnostics and echoed query text never
    count."""
    entities = []
    for line in stdout.splitlines():
        m = ENTITY_LINE.match(line.strip())
        if m:
            entities.append({"name": m.group(1), "kind": m.group(2), "id": m.group(3)})
    hit = any(e["name"] == wanted_symbol for e in entities)
    return {"records": entities, "hit": hit, "heading_only": not entities,
            "unresolved": "[Unresolved]" in stdout}


def measure(cmd, ws, wanted_symbol):
    code, out, err, ms = run_split(cmd, ws, timeout=120)
    scored = score_context(out, wanted_symbol)
    return {"bytes": len(out.encode()), "stderr_bytes": len(err.encode()),
            "wall_ms": round(ms, 1), "hit": scored["hit"],
            "records": len(scored["records"]), "heading_only": scored["heading_only"],
            "unresolved": scored["unresolved"], "exit_code": code,
            "head": out.strip().splitlines()[:2]}


def score_search(stdout, wanted_intent):
    """Knot references a search returned, and whether the ground-truth
    intent is among them. Returns the first surfaced knot id so the next
    step can be derived from the search output alone."""
    refs = []
    for line in stdout.splitlines():
        m = SEARCH_LINE.match(line)
        if m and "|" in line:
            refs.append({"knot": m.group(1), "intent": m.group(2)})
    hit = any(wanted_intent in r["intent"] for r in refs)
    return {"refs": refs, "hit": hit,
            "first_knot": refs[0]["knot"] if refs else None}


def measure_search(ws, term, wanted_intent):
    code, out, err, ms = run_split(["nool", "query", "search", term, "--compact"], ws, timeout=120)
    scored = score_search(out, wanted_intent)
    return {"bytes": len(out.encode()), "stderr_bytes": len(err.encode()),
            "wall_ms": round(ms, 1), "hit": scored["hit"], "records": len(scored["refs"]),
            "first_knot": scored["first_knot"], "exit_code": code,
            "head": out.strip().splitlines()[:2]}


def measure_materialize(ws, knot, wanted_signature):
    """The derived second step: materialize the knot the search surfaced
    and look for the function's own definition in the reconstructed
    source. A missing knot (search returned nothing) is a miss, not an
    error."""
    if not knot:
        return {"bytes": 0, "wall_ms": 0.0, "hit": False, "exit_code": None,
                "derived_from": None}
    code, out, err, ms = run_split(["nool", "query", "materialize", knot], ws, timeout=120)
    return {"bytes": len(out.encode()), "stderr_bytes": len(err.encode()),
            "wall_ms": round(ms, 1), "hit": wanted_signature in out,
            "exit_code": code, "derived_from": knot}


def baseline_grep_and_read(ws, term, wanted_signature):
    """Grep for the term, then read every matching file in full — the
    canonical agent pattern in a plain git repo. The hit is the function's
    own definition appearing in what was read."""
    t0 = time.monotonic()
    code, out, _ = run(["grep", "-rn", "-i", term, "--include=*.go", "."], ws)
    total = len(out.encode())
    files = sorted({line.split(":")[0] for line in out.splitlines() if ":" in line})
    blob = out
    for f in files:
        content = (ws / f).read_text()
        total += len(content.encode())
        blob += content
    ms = (time.monotonic() - t0) * 1000.0
    return {"bytes": total, "wall_ms": round(ms, 1), "hit": wanted_signature in blob,
            "files_read": len(files)}


def baseline_grep_bounded(ws, term, wanted_signature, context_lines=6):
    """A tuned grep: matches plus a bounded window of context, no whole-file
    reads. The information budget an agent with `rg -C` actually pays."""
    code, out, _, ms = run_split(
        ["grep", "-rn", "-i", "-C", str(context_lines), term, "--include=*.go", "."], ws)
    return {"bytes": len(out.encode()), "wall_ms": round(ms, 1),
            "hit": wanted_signature in out, "context_lines": context_lines}


def main():
    signature = f"func {GROUND_TRUTH_FUNC}("
    with TempRoot("b6") as root:
        ws = build_repo(root)
        # Search returns knot references (id | intent | thread), not code —
        # its hit criterion is the ground-truth INTENT surfacing among the
        # returned references. The chained flow materializes the knot the
        # search surfaced: its second step is derived from the first's
        # output, so the ground truth never leaks into the experiment.
        search = measure_search(ws, "rate limiting",
                                "rate limiting for client request budgets")
        materialized = measure_materialize(ws, search["first_knot"], signature)
        ctx_symbol = measure(
            ["nool", "query", "context",
             f"{GROUND_TRUTH_FILE}#{GROUND_TRUTH_FUNC}", "--depth", "1",
             "--compact"], ws, GROUND_TRUTH_FUNC)
        negative = measure(
            ["nool", "query", "context",
             f"{GROUND_TRUTH_FILE}#{NEGATIVE_SYMBOL}", "--depth", "1",
             "--compact"], ws, NEGATIVE_SYMBOL)
        results = {
            "nool_query_search": search,
            "nool_query_context_file": measure(
                ["nool", "query", "context", GROUND_TRUTH_FILE, "--depth", "1",
                 "--compact"], ws, GROUND_TRUTH_FUNC),
            "nool_query_context_symbol": ctx_symbol,
            "nool_query_context_nonexistent_symbol": negative,
            "nool_search_then_materialize": {
                "bytes": search["bytes"] + materialized["bytes"],
                "wall_ms": round(search["wall_ms"] + materialized["wall_ms"], 1),
                "hit": search["hit"] and materialized["hit"],
                "derived_from": materialized["derived_from"],
            },
            "baseline_grep_read": baseline_grep_and_read(ws, "rate", signature),
            "baseline_grep_bounded": baseline_grep_bounded(ws, "rate", signature),
            "controls": {
                "negative_symbol_not_hit": not negative["hit"],
                "negative_symbol_reported_unresolved": negative["unresolved"],
                "symbol_answer_has_records": not ctx_symbol["heading_only"],
            },
        }
        # Repo-scale context for reference: total bytes an agent reading
        # everything would ingest.
        total = sum(len(p.read_bytes()) for p in ws.glob("*.go"))
        results["whole_repo_go_bytes"] = total
    emit("b6_context_retrieval", {
        "config": {"n_files": N_FILES, "funcs_per_file": FUNCS_PER_FILE,
                   "ground_truth": f"{GROUND_TRUTH_FILE}#{GROUND_TRUTH_FUNC}",
                   "negative_control": f"{GROUND_TRUTH_FILE}#{NEGATIVE_SYMBOL}",
                   "hit_criterion": "entity record naming the function (stdout only); "
                                    "headings and echoed query text never count"},
        "queries": results,
    })


if __name__ == "__main__":
    main()
