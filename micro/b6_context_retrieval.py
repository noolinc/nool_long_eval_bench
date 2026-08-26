"""B6 — Semantic context retrieval (the "structured context" claim).

A repo with F files x G functions is built knot-by-knot with recorded
intents; one feature ("rate limiting") has known ground-truth locations.
An agent needing that context can either:

  nool arm : `nool query search "<intent>"` and `nool query context <node>`
  baseline : what agents actually do in a git repo — grep for terms, then
             read every matching file in full.

Metrics per query: bytes the agent must ingest, wall ms, and hit (does the
returned context contain the ground-truth function?). Bytes are reported as
bytes — no token conversion.
"""

import time

from common import TempRoot, emit, make_workspace, nool_land, run

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


def measure(cmd, ws, contains):
    t0 = time.monotonic()
    code, out, _ = run(cmd, ws, timeout=120)
    ms = (time.monotonic() - t0) * 1000.0
    return {"bytes": len(out.encode()), "wall_ms": round(ms, 1),
            "hit": contains in out, "exit_code": code,
            "head": out.strip().splitlines()[:2]}


def baseline_grep_and_read(ws, term, contains):
    """Grep for the term, then read every matching file in full — the
    canonical agent pattern in a plain git repo."""
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
    return {"bytes": total, "wall_ms": round(ms, 1), "hit": contains in blob,
            "files_read": len(files)}


def main():
    with TempRoot("b6") as root:
        ws = build_repo(root)
        # Search returns knot references (id | intent | thread), not code —
        # its hit criterion is the ground-truth INTENT surfacing. The
        # realistic agent flow is search -> context on the surfaced node, so
        # the chained cost is also reported.
        search = measure(
            ["nool", "query", "search", "rate limiting", "--compact"],
            ws, "rate limiting for client request budgets")
        ctx_symbol = measure(
            ["nool", "query", "context",
             f"{GROUND_TRUTH_FILE}#{GROUND_TRUTH_FUNC}", "--depth", "1",
             "--compact"], ws, GROUND_TRUTH_FUNC)
        results = {
            "nool_query_search": search,
            "nool_query_context_file": measure(
                ["nool", "query", "context", GROUND_TRUTH_FILE, "--depth", "1",
                 "--compact"], ws, GROUND_TRUTH_FUNC),
            "nool_query_context_symbol": ctx_symbol,
            "nool_search_then_context": {
                "bytes": search["bytes"] + ctx_symbol["bytes"],
                "wall_ms": round(search["wall_ms"] + ctx_symbol["wall_ms"], 1),
                "hit": search["hit"] and ctx_symbol["hit"],
            },
            "baseline_grep_read": baseline_grep_and_read(
                ws, "rate", GROUND_TRUTH_FUNC),
        }
        # Repo-scale context for reference: total bytes an agent reading
        # everything would ingest.
        total = sum(len(p.read_bytes()) for p in ws.glob("*.go"))
        results["whole_repo_go_bytes"] = total
    emit("b6_context_retrieval", {
        "config": {"n_files": N_FILES, "funcs_per_file": FUNCS_PER_FILE,
                   "ground_truth": f"{GROUND_TRUTH_FILE}#{GROUND_TRUTH_FUNC}"},
        "queries": results,
    })


if __name__ == "__main__":
    main()
