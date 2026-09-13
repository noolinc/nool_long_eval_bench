"""B9 — Blast-radius fidelity across every built-in language (B8's shapes, per language).

For each language: chain (util <- helper <- handler, + unrelated), star (core <- 3 leaves,
+ unrelated), causal pollution (a, then 4 unrelated). Files land one at a time with
`nool propose --all --fast --solidify`; ground truth is the dependents closure by
construction. R(target) = dependents listed by `nool query blast-radius` plus the paths of
the descendant knots it lists, intersected with the scenario universe.

Markup/config formats have no dependency semantics in Nool: they run pollution only and
must report nothing.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from common import ENV, emit

ONLY = set(os.environ["B9_ONLY"].split(",")) if os.environ.get("B9_ONLY") else None


def run(cmd, cwd, timeout=120):
    p = subprocess.run(cmd, cwd=str(cwd), env=ENV, timeout=timeout,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout


def cap(base):
    return "".join(w[:1].upper() + w[1:] for w in base.split("_")) if "_" not in base else base[:1].upper() + base[1:]


# ---------------------------------------------------------------------------
# Language templates.  file(base) -> relpath; sym(base) -> symbol; leaf(base);
# dep(base, [dep_base, ...]); scaffold -> landed with the first file;
# trailer(bases) -> landed with the last file; extra_dependents -> added to
# every non-empty and empty G (e.g. a crate root that declares every module).
# ---------------------------------------------------------------------------
def lang(ext, leaf, dep, file=None, sym=None, scaffold=None, trailer=None,
         extra_dependents=(), pollution_only=False):
    return dict(
        ext=ext,
        file=file or (lambda b: f"{b}.{ext}"),
        sym=sym or (lambda b: b),
        leaf=leaf, dep=dep, scaffold=scaffold or {}, trailer=trailer,
        extra_dependents=set(extra_dependents), pollution_only=pollution_only,
    )


LANGS = {
    "python": lang("py",
        leaf=lambda b: f"def {b}():\n    return 1\n",
        dep=lambda b, ds: "".join(f"from {d} import {d}\n" for d in ds) + f"\n\ndef {b}():\n    return " + " + ".join(f"{d}()" for d in ds) + "\n"),
    "javascript": lang("js",
        leaf=lambda b: f"export function {b}() {{ return 1; }}\n",
        dep=lambda b, ds: "".join(f'import {{ {d} }} from "./{d}.js";\n' for d in ds) + f"\nexport function {b}() {{ return " + " + ".join(f"{d}()" for d in ds) + "; }\n"),
    "typescript": lang("ts",
        leaf=lambda b: f"export function {b}(): number {{ return 1; }}\n",
        dep=lambda b, ds: "".join(f'import {{ {d} }} from "./{d}";\n' for d in ds) + f"\nexport function {b}(): number {{ return " + " + ".join(f"{d}()" for d in ds) + "; }\n"),
    "java": lang("java", file=lambda b: f"{cap(b)}.java", sym=cap,
        leaf=lambda b: f"public class {cap(b)} {{\n    public int value() {{ return 1; }}\n}}\n",
        dep=lambda b, ds: f"public class {cap(b)} {{\n" + "".join(f"    private final {cap(d)} {d}Dep = new {cap(d)}();\n" for d in ds) + "    public int value() { return " + " + ".join(f"{d}Dep.value()" for d in ds) + "; }\n}\n"),
    "csharp": lang("cs", file=lambda b: f"{cap(b)}.cs", sym=cap,
        leaf=lambda b: f"public class {cap(b)} {{\n    public int Value() {{ return 1; }}\n}}\n",
        dep=lambda b, ds: f"public class {cap(b)} {{\n" + "".join(f"    private readonly {cap(d)} {d}Dep = new {cap(d)}();\n" for d in ds) + "    public int Value() { return " + " + ".join(f"{d}Dep.Value()" for d in ds) + "; }\n}\n"),
    "cpp": lang("hpp",
        leaf=lambda b: f"#pragma once\ninline int {b}() {{ return 1; }}\n",
        dep=lambda b, ds: "#pragma once\n" + "".join(f'#include "{d}.hpp"\n' for d in ds) + f"inline int {b}() {{ return " + " + ".join(f"{d}()" for d in ds) + "; }\n"),
    "c": lang("h",
        leaf=lambda b: f"#ifndef {b.upper()}_H\n#define {b.upper()}_H\nstatic inline int {b}(void) {{ return 1; }}\n#endif\n",
        dep=lambda b, ds: f"#ifndef {b.upper()}_H\n#define {b.upper()}_H\n" + "".join(f'#include "{d}.h"\n' for d in ds) + f"static inline int {b}(void) {{ return " + " + ".join(f"{d}()" for d in ds) + "; }\n#endif\n"),
    "php": lang("php",
        leaf=lambda b: f"<?php\nfunction {b}() {{ return 1; }}\n",
        dep=lambda b, ds: "<?php\n" + "".join(f"require_once '{d}.php';\n" for d in ds) + f"function {b}() {{ return " + " + ".join(f"{d}()" for d in ds) + "; }\n"),
    "rust": lang("rs", file=lambda b: f"src/{b}.rs",
        leaf=lambda b: f"pub fn {b}() -> u8 {{ 1 }}\n",
        dep=lambda b, ds: "".join(f"use crate::{d}::{d};\n" for d in ds) + f"\npub fn {b}() -> u8 {{ " + " + ".join(f"{d}()" for d in ds) + " }\n",
        scaffold={"Cargo.toml": '[package]\nname = "bench"\nversion = "0.1.0"\nedition = "2021"\n\n[lib]\npath = "src/lib.rs"\n'},
        trailer=lambda bases: {"src/lib.rs": "".join(f"pub mod {b};\n" for b in bases)},
        extra_dependents=("src/lib.rs",)),
    "kotlin": lang("kt", file=lambda b: f"{cap(b)}.kt", sym=cap,
        leaf=lambda b: f"class {cap(b)} {{\n    fun value(): Int = 1\n}}\n",
        dep=lambda b, ds: f"class {cap(b)} {{\n" + "".join(f"    val {d}Dep: {cap(d)} = {cap(d)}()\n" for d in ds) + "    fun value(): Int = " + " + ".join(f"{d}Dep.value()" for d in ds) + "\n}\n"),
    "swift": lang("swift", file=lambda b: f"{cap(b)}.swift", sym=cap,
        leaf=lambda b: f"final class {cap(b)} {{\n    func value() -> Int {{ return 1 }}\n}}\n",
        dep=lambda b, ds: f"final class {cap(b)} {{\n" + "".join(f"    let {d}Dep: {cap(d)} = {cap(d)}()\n" for d in ds) + "    func value() -> Int { return " + " + ".join(f"{d}Dep.value()" for d in ds) + " }\n}\n"),
    "ruby": lang("rb",
        leaf=lambda b: f"def {b}\n  1\nend\n",
        dep=lambda b, ds: "".join(f"require_relative '{d}'\n" for d in ds) + f"\ndef {b}\n  " + " + ".join(ds) + "\nend\n"),
    "dart": lang("dart",
        leaf=lambda b: f"int {b}() => 1;\n",
        dep=lambda b, ds: "".join(f"import '{d}.dart';\n" for d in ds) + f"\nint {b}() => " + " + ".join(f"{d}()" for d in ds) + ";\n"),
    "scala": lang("scala", file=lambda b: f"{cap(b)}.scala", sym=cap,
        leaf=lambda b: f"class {cap(b)} {{\n  def value: Int = 1\n}}\n",
        dep=lambda b, ds: f"class {cap(b)} {{\n" + "".join(f"  val {d}Dep: {cap(d)} = new {cap(d)}()\n" for d in ds) + "  def value: Int = " + " + ".join(f"{d}Dep.value" for d in ds) + "\n}\n"),
    "lua": lang("lua",
        leaf=lambda b: f"local M = {{}}\nfunction M.{b}() return 1 end\nreturn M\n",
        dep=lambda b, ds: "".join(f'local {d} = require("{d}")\n' for d in ds) + f"local M = {{}}\nfunction M.{b}() return " + " + ".join(f"{d}.{d}()" for d in ds) + " end\nreturn M\n"),
    "r": lang("r",
        leaf=lambda b: f"{b} <- function() 1\n",
        dep=lambda b, ds: "".join(f'source("{d}.r")\n' for d in ds) + f"{b} <- function() " + " + ".join(f"{d}()" for d in ds) + "\n"),
    "shell": lang("sh",
        leaf=lambda b: f"{b}() {{ echo 1; }}\n",
        dep=lambda b, ds: "".join(f"source ./{d}.sh\n" for d in ds) + f"{b}() {{ " + "; ".join(ds) + "; }\n"),
    "powershell": lang("ps1",
        leaf=lambda b: f"function {b} {{ 1 }}\n",
        dep=lambda b, ds: "".join(f". ./{d}.ps1\n" for d in ds) + f"function {b} {{ " + "; ".join(ds) + " }\n"),
    "objective-c": lang("m",
        leaf=lambda b: f"int {b}(void) {{ return 1; }}\n",
        dep=lambda b, ds: "".join(f'#import "{d}.m"\n' for d in ds) + f"int {b}(void) {{ return " + " + ".join(f"{d}()" for d in ds) + "; }\n"),
    "elixir": lang("ex", sym=cap,
        leaf=lambda b: f"defmodule {cap(b)} do\n  def value, do: 1\nend\n",
        dep=lambda b, ds: f"defmodule {cap(b)} do\n" + "".join(f"  alias {cap(d)}\n" for d in ds) + "  def value, do: " + " + ".join(f"{cap(d)}.value()" for d in ds) + "\nend\n"),
    "erlang": lang("erl",
        leaf=lambda b: f"-module({b}).\n-export([{b}/0]).\n{b}() -> 1.\n",
        dep=lambda b, ds: f"-module({b}).\n-export([{b}/0]).\n" + "".join(f"-import({d}, [{d}/0]).\n" for d in ds) + f"{b}() -> " + " + ".join(f"{d}()" for d in ds) + ".\n"),
    "clojure": lang("clj",
        leaf=lambda b: f"(ns {b})\n(defn {b} [] 1)\n",
        dep=lambda b, ds: f"(ns {b} (:require " + " ".join(f"[{d} :refer [{d}]]" for d in ds) + f"))\n(defn {b} [] (+ " + " ".join(f"({d})" for d in ds) + "))\n"),
    "svelte": lang("svelte",
        leaf=lambda b: f"<script>\n  export function {b}() {{ return 1; }}\n</script>\n",
        dep=lambda b, ds: "<script>\n" + "".join(f'  import {{ {d} }} from "./{d}.svelte";\n' for d in ds) + f"  export function {b}() {{ return " + " + ".join(f"{d}()" for d in ds) + "; }\n</script>\n"),
    "css": lang("css",
        leaf=lambda b: f".{b} {{ color: red; }}\n",
        dep=lambda b, ds: "".join(f'@import "{d}.css";\n' for d in ds) + f".{b} {{ color: blue; }}\n"),
    "html": lang("html", pollution_only=True, leaf=lambda b: f"<!doctype html>\n<title>{b}</title>\n<p>{b}</p>\n", dep=None),
    "json": lang("json", pollution_only=True, leaf=lambda b: json.dumps({"name": b, "value": 1}, indent=1) + "\n", dep=None),
    "markdown": lang("md", pollution_only=True, leaf=lambda b: f"# {b}\n\nStandalone note.\n", dep=None),
    "toml": lang("toml", pollution_only=True, leaf=lambda b: f"[{b}]\nvalue = 1\n", dep=None),
    "yaml": lang("yaml", pollution_only=True, leaf=lambda b: f"{b}:\n  value: 1\n", dep=None),
    "xml": lang("xml", pollution_only=True, leaf=lambda b: f'<?xml version="1.0"?>\n<{b}><value>1</value></{b}>\n', dep=None),
}

# (name, ordered [(base, [dep_bases])], ground truth base->set(bases))
SCENARIOS = [
    ("chain", [("util", []), ("helper", ["util"]), ("handler", ["helper"]), ("unrelated", [])],
     {"util": {"helper", "handler"}, "helper": {"handler"}, "handler": set(), "unrelated": set()}),
    ("star", [("core", []), ("leaf_0", ["core"]), ("leaf_1", ["core"]), ("leaf_2", ["core"]), ("unrelated_star", [])],
     {"core": {"leaf_0", "leaf_1", "leaf_2"}, "leaf_0": set(), "unrelated_star": set()}),
    ("pollution", [("a", [])] + [(f"pollute_{i:02d}", []) for i in range(4)],
     {"a": set()}),
]


def workspace(root, name):
    ws = Path(root) / name
    ws.mkdir(parents=True)
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "config", "user.email", "bench@nool-benchmarks.local"], ["git", "config", "user.name", "Bench"]):
        code, out = run(cmd, ws)
        assert code == 0, out
    code, out = run(["nool", "init"], ws)
    assert code == 0, out
    (ws / ".gitignore").write_text(".nool/\nLibrary/\n.cache/\n")
    return ws


def land(ws, intent):
    code, out = run(["nool", "propose", "--all", "--intent", intent, "--fast", "--solidify", "--compact"], ws)
    return code, out


def parse_query(out):
    dependents, knots = set(), set()
    for line in out.splitlines():
        if "Dependents via entity graph:" in line:
            dependents.update(s.strip() for s in line.split(":", 1)[1].split(",") if s.strip())
        elif " @ " in line:
            knots.add(line.split(" @ ", 1)[1].split()[0].strip().rstrip(","))
    m = re.search(r"Target .*?:\s+(\d+)\s+descendants", out)
    return dependents, knots, (int(m.group(1)) if m else None)


def parse_debug(out):
    m = re.search(r"BLAST_TOPOLOGY:.*", out)
    if not m:
        return None
    line = m.group(0)
    g = lambda k: (re.search(k + r"=(\d+)", line) or [None, None])[1]
    return {"risk": g("risk"), "dependents": g("dependents"), "symbol_reachable": g("symbol_reachable"), "unrelated_later": g("unrelated_later"), "line": line[:400]}


def metrics(R, G, universe):
    TP, FP, FN = len(R & G), len(R - G), len(G - R)
    TN = len(universe - (R | G))
    return {"TP": TP, "FP": FP, "FN": FN, "TN": TN,
            "FPR": round(FP / (FP + TN), 4) if FP + TN else 0.0,
            "recall": round(TP / len(G), 4) if G else (1.0 if not R else 0.0),
            "precision": round(TP / len(R), 4) if R else (1.0 if not G else 0.0)}


def run_language(root, name, L):
    report = {"language": name, "scenarios": [], "errors": []}
    for sname, order, truth in SCENARIOS:
        if L["pollution_only"] and sname != "pollution":
            continue
        ws = workspace(root, f"{name}_{sname}")
        bases = [b for b, _ in order]
        universe = {L["file"](b) for b in bases} | set(L["extra_dependents"])
        try:
            for i, (b, deps) in enumerate(order):
                if i == 0:
                    for rel, content in L["scaffold"].items():
                        p = ws / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
                p = ws / L["file"](b); p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(L["leaf"](b) if not deps else L["dep"](b, deps))
                code, out = land(ws, f"add {b}")
                if code != 0:
                    raise RuntimeError(f"land {b} failed ({code}): {out[-600:]}")
            # A crate root that declares every module lands as its own knot, after
            # all of them exist: bundling it with the last module made that knot
            # touch both a dependent (the root) and an unrelated file.
            if L["trailer"]:
                for rel, content in L["trailer"](bases).items():
                    q = ws / rel; q.parent.mkdir(parents=True, exist_ok=True); q.write_text(content)
                code, out = land(ws, "add module root")
                if code != 0:
                    raise RuntimeError(f"land trailer failed ({code}): {out[-600:]}")
            rows = []
            for tb, G_b in truth.items():
                target = L["file"](tb)
                G = {L["file"](g) for g in G_b} | set(L["extra_dependents"])
                G.discard(target)
                t0 = time.monotonic(); code_q, out_q = run(["nool", "query", "blast-radius", target], ws); q_ms = (time.monotonic() - t0) * 1000
                dependents, knots, dc = parse_query(out_q)
                R = (dependents | knots) & universe
                R.discard(target)
                t0 = time.monotonic(); code_d, out_d = run(["nool", "debug", "blast-radius", target, "--compact"], ws); d_ms = (time.monotonic() - t0) * 1000
                rows.append({"target": target, "G": sorted(G), "R": sorted(R), "dependents": sorted(dependents), "descendant_paths": sorted(knots),
                             "metrics": metrics(R, G, universe), "query_exit": code_q, "debug": parse_debug(out_d), "debug_exit": code_d,
                             "query_ms": round(q_ms, 1), "debug_ms": round(d_ms, 1)})
            report["scenarios"].append({"scenario": sname, "universe": sorted(universe), "targets": rows})
        except Exception as e:  # keep going; the error is the finding
            report["errors"].append({"scenario": sname, "error": str(e)[:800]})
    return report


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="noolbench_ml_") as root:
        for name, L in LANGS.items():
            if ONLY and name not in ONLY:
                continue
            t0 = time.monotonic()
            rep = run_language(root, name, L)
            rep["seconds"] = round(time.monotonic() - t0, 1)
            results.append(rep)
            rows = [t for s in rep["scenarios"] for t in s["targets"]]
            fpr = sum(t["metrics"]["FPR"] for t in rows) / len(rows) if rows else None
            rec = [t["metrics"]["recall"] for t in rows if t["G"]]
            recall = sum(rec) / len(rec) if rec else None
            print(f"[{name:12s}] targets={len(rows):2d} meanFPR={fpr if fpr is None else round(fpr,3)} meanRecall={recall if recall is None else round(recall,3)} errors={len(rep['errors'])} {rep['seconds']}s", flush=True)
            for t in rows:
                if t["metrics"]["FP"] or t["metrics"]["FN"]:
                    print(f"     {t['target']}: G={t['G']} R={t['R']}", flush=True)
            for e in rep["errors"]:
                print(f"     ERROR {e['scenario']}: {e['error'][:200]}", flush=True)
    summary = {}
    for rep in results:
        rows = [t for s in rep["scenarios"] for t in s["targets"]]
        rec = [t["metrics"]["recall"] for t in rows if t["G"]]
        summary[rep["language"]] = {
            "targets": len(rows),
            "mean_FPR": round(sum(t["metrics"]["FPR"] for t in rows) / len(rows), 4) if rows else None,
            "mean_recall": round(sum(rec) / len(rec), 4) if rec else None,
            "errors": len(rep["errors"]),
        }
    emit("b9_blast_multilang", {
        "config": {"scenarios": [s[0] for s in SCENARIOS], "languages": [r["language"] for r in results],
                   "mode": "propose --all --fast --solidify, one file per knot",
                   "ground_truth": "dependents closure by construction; markup/config formats run pollution only"},
        "summary": summary,
        "results": results,
    })


if __name__ == "__main__":
    main()
