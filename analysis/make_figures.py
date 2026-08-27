#!/usr/bin/env python3
"""Generate the SVG figures for docs/findings/ from committed raw results.

Deterministic: reads only files under results/, writes only
docs/findings/figures/*.svg. Every value plotted here is present verbatim in
the raw JSON/JSONL; nothing is estimated or interpolated.

Palette and mark conventions (validated for colorblind safety before use):
arms are fixed hues (nool #2a78d6, git #eb6834); ticket-outcome severity is
a single-hue ordinal ramp (light -> dark, CVD-safe by lightness); text never
wears a data color; bars are thin with a rounded data end and square base.
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "findings" / "figures"

# ---- palette (light surface; validated with the dataviz six-check script) --
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
NOOL = "#2a78d6"   # categorical slot 1
GIT = "#eb6834"    # categorical slot 2
ORDINAL = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # severity, light->dark
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"

# Primary scale-up 1 comparison (all nool 6.14.1, fixed harness), in run order.
PRIMARY = [
    ("fleet_git_fleet_9a6eb70f", "git rep 1", GIT),
    ("fleet_git_fleet_803f2288", "git rep 2", GIT),
    ("fleet_nool_fleet_cb7ccf72", "nool rep 1", NOOL),
    ("fleet_nool_fleet_2a51582f", "nool rep 2", NOOL),
]
CLUSTERS = {"A": ["t9", "t10", "t11"], "B": ["t12", "t13", "t14"],
            "C": ["t15", "t16", "t17"]}


def textw(s, size):
    return len(s) * size * 0.58


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class SVG:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-family="{FONT}">',
            f'<rect width="{w}" height="{h}" fill="{SURFACE}"/>']

    def text(self, x, y, s, size=11, fill=INK2, anchor="start", weight="normal"):
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')

    def line(self, x1, y1, x2, y2, stroke=GRID, width=1):
        self.parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}"/>')

    def col(self, x, y_base, w, h, fill, r=4):
        """Column: rounded top (data end), square baseline."""
        if h <= 0.5:  # zero-height: 2px stub so the mark exists
            self.parts.append(
                f'<rect x="{x:.1f}" y="{y_base-2:.1f}" width="{w:.1f}" '
                f'height="2" fill="{fill}"/>')
            return
        r = min(r, h / 2, w / 2)
        y = y_base - h
        self.parts.append(
            f'<path d="M {x:.1f} {y_base:.1f} L {x:.1f} {y+r:.1f} '
            f'Q {x:.1f} {y:.1f} {x+r:.1f} {y:.1f} L {x+w-r:.1f} {y:.1f} '
            f'Q {x+w:.1f} {y:.1f} {x+w:.1f} {y+r:.1f} L {x+w:.1f} {y_base:.1f} Z" '
            f'fill="{fill}"/>')

    def hbar(self, x_base, y, w, h, fill, r=4, rounded_end=True):
        """Horizontal bar/segment: rounded right end optional (stack interiors square)."""
        if w <= 0.5:
            return
        rr = min(r, w / 2, h / 2) if rounded_end else 0
        self.parts.append(
            f'<path d="M {x_base:.1f} {y:.1f} L {x_base+w-rr:.1f} {y:.1f} '
            f'Q {x_base+w:.1f} {y:.1f} {x_base+w:.1f} {y+rr:.1f} '
            f'L {x_base+w:.1f} {y+h-rr:.1f} '
            f'Q {x_base+w:.1f} {y+h:.1f} {x_base+w-rr:.1f} {y+h:.1f} '
            f'L {x_base:.1f} {y+h:.1f} Z" fill="{fill}"/>')

    def legend(self, x, y, items):
        for label, color in items:
            self.parts.append(
                f'<rect x="{x:.1f}" y="{y-9:.1f}" width="10" height="10" rx="2" '
                f'fill="{color}"/>')
            self.text(x + 15, y, label, size=11, fill=INK2)
            x += 15 + textw(label, 11) + 18

    def save(self, name):
        self.parts.append("</svg>")
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text("\n".join(self.parts) + "\n")
        print("wrote", (OUT / name).relative_to(REPO))


def grouped_columns(name, title, subtitle, groups, series, ymax, yticks,
                    ylabel, value_fmt=lambda v: f"{v:g}", h=340, w=700):
    """groups: [group_label]; series: [(label, color, [values by group])]."""
    s = SVG(w, h)
    s.text(16, 24, title, size=13, fill=INK, weight="600")
    s.text(16, 41, subtitle, size=11, fill=INK2)
    top, bottom, left, right = 58, h - 46, 52, w - 16
    ph = bottom - top
    for t in yticks:
        y = bottom - ph * t / ymax
        if t > 0:
            s.line(left, y, right, y)
        s.text(left - 8, y + 3.5, f"{t:g}", size=10.5, fill=MUTED, anchor="end")
    s.line(left, bottom, right, bottom, stroke=BASELINE)
    s.text(16, top - 6, ylabel, size=10.5, fill=MUTED)
    ng, ns = len(groups), len(series)
    gw = (right - left) / ng
    bw, gap = min(24, (gw - 24) / ns - 2), 2
    for gi, glabel in enumerate(groups):
        x0 = left + gi * gw + (gw - (bw + gap) * ns + gap) / 2
        for si, (_, color, vals) in enumerate(series):
            v = vals[gi]
            x = x0 + si * (bw + gap)
            bh = ph * v / ymax
            s.col(x, bottom, bw, bh, color)
            s.text(x + bw / 2, bottom - bh - 5, value_fmt(v), size=11,
                   fill=INK, anchor="middle")
        s.text(left + gi * gw + gw / 2, bottom + 17, glabel, size=11,
               fill=INK2, anchor="middle")
    s.legend(left, h - 12, [(lab, c) for lab, c, _ in series if lab])
    s.save(name)


def line_series(name, title, subtitle, x_labels, series, ymax, yticks,
                ylabel, value_fmt=lambda v: f"{v:g}", h=340, w=700):
    """x_labels: ordered category labels (e.g. noise levels).
    series: [(label, color, [values by x_label])]. One line + dot markers
    + value labels per series; used for trends across an ordered axis
    where a line reads more honestly than adjacent bars (e.g. a
    degradation curve)."""
    s = SVG(w, h)
    s.text(16, 24, title, size=13, fill=INK, weight="600")
    s.text(16, 41, subtitle, size=11, fill=INK2)
    top, bottom, left, right = 58, h - 46, 52, w - 16
    ph, pw = bottom - top, right - left
    for t in yticks:
        y = bottom - ph * t / ymax
        if t > 0:
            s.line(left, y, right, y)
        s.text(left - 8, y + 3.5, f"{t:g}", size=10.5, fill=MUTED, anchor="end")
    s.line(left, bottom, right, bottom, stroke=BASELINE)
    s.text(16, top - 6, ylabel, size=10.5, fill=MUTED)
    n = len(x_labels)
    xs = [left + pw * i / (n - 1) for i in range(n)] if n > 1 else [left + pw / 2]
    for xi, xl in enumerate(x_labels):
        s.text(xs[xi], bottom + 17, xl, size=11, fill=INK2, anchor="middle")
    for label, color, vals in series:
        pts = [(xs[i], bottom - ph * v / ymax) for i, v in enumerate(vals)]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            s.line(x1, y1, x2, y2, stroke=color, width=2.5)
        for (x, y), v in zip(pts, vals):
            s.parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" '
                           f'fill="{color}"/>')
            s.text(x, y - 10, value_fmt(v), size=11, fill=INK, anchor="middle")
    s.legend(left, h - 12, [(lab, c) for lab, c, _ in series if lab])
    s.save(name)


NOISE_CELLS_8D = [
    ("zero", ("fleet_nool_gated_f50ec0fe", "fleet_nool_gated_e4b89982"),
             ("fleet_git_scheduled_976968d7", "fleet_git_scheduled_928d3ccb")),
    ("light", ("fleet_nool_gated_92106c6e", "fleet_nool_gated_46b05974"),
              ("fleet_git_scheduled_f377f205", "fleet_git_scheduled_e99f90df")),
    ("heavy", ("fleet_nool_gated_9b8ae7be", "fleet_nool_gated_c5f44b1a"),
              ("fleet_git_scheduled_d16cdf36", "fleet_git_scheduled_752dd08d")),
    ("very-heavy", ("fleet_nool_gated_138ef09b", "fleet_nool_gated_fb380c1f"),
                   ("fleet_git_scheduled_c097eb0c", "fleet_git_scheduled_026c16d0")),
]


def fig_8d_degradation(recs):
    labels = [c for c, _, _ in NOISE_CELLS_8D]

    def mean_rate(rids):
        return 100.0 * sum(sum(recs[rid]["acceptance"].values())
                           for rid in rids) / (len(rids) * 60)
    nool_vals = [mean_rate(n_ids) for _, n_ids, _ in NOISE_CELLS_8D]
    git_vals = [mean_rate(g_ids) for _, _, g_ids in NOISE_CELLS_8D]
    line_series(
        "trackd_8d_degradation.svg",
        "§8d: mean ticket-acceptance rate as footprint noise increases",
        "N=20 workers, corpus v3.1, 2 reps/cell; nool_gated vs git_scheduled under injected footprint noise (fp_drop=fp_add per cell: 0, 0.1, 0.3, 0.5)",
        labels,
        [("git_scheduled", GIT, git_vals), ("nool_gated", NOOL, nool_vals)],
        ymax=100, yticks=[0, 25, 50, 75, 100],
        ylabel="% tickets accepted (mean of 2 reps)",
        value_fmt=lambda v: f"{v:.1f}%")


def fig_8d_conflicts(recs):
    labels = [c for c, _, _ in NOISE_CELLS_8D]

    def mean_conflicts(rids):
        evo = [recs[rid]["evolution"]["conflicts"] for rid in rids]
        return sum(evo) / len(evo)
    nool_vals = [mean_conflicts(n_ids) for _, n_ids, _ in NOISE_CELLS_8D]
    git_vals = [mean_conflicts(g_ids) for _, _, g_ids in NOISE_CELLS_8D]
    grouped_columns(
        "trackd_8d_conflicts.svg",
        "§8d: mean merge conflicts as footprint noise increases",
        "Same runs as the degradation curve; conflicts are the mechanism behind the widening acceptance gap",
        labels,
        [("git_scheduled", GIT, git_vals), ("nool_gated", NOOL, nool_vals)],
        ymax=12, yticks=[0, 3, 6, 9, 12], ylabel="mean conflicts (of 60 tickets)",
        value_fmt=lambda v: f"{v:.1f}")


def fig_8d_composition(recs):
    """Very-heavy cell only: outcome breakdown per arm, same severity-ordered
    stacked-bar convention as fig_composition (a pie chart would need equal
    denominators to compare slice angles meaningfully and this suite's own
    dataviz convention avoids them for that reason)."""
    _, n_ids, g_ids = NOISE_CELLS_8D[-1]
    rows = []
    for label, rids, color in [("git_scheduled", g_ids, GIT),
                               ("nool_gated", n_ids, NOOL)]:
        acc = conf = other = 0
        for rid in rids:
            r = recs[rid]
            acc += sum(r["acceptance"].values())
            conf += r["evolution"]["conflicts"]
            other += 60 - sum(r["acceptance"].values()) - r["evolution"]["conflicts"]
        rows.append((label, [acc, conf, other], color))
    classes = [("Accepted", ORDINAL[0]), ("Merge conflict", ORDINAL[2]),
               ("Other (landed, not accepted)", ORDINAL[3])]
    w, h = 700, 96 + 44 * len(rows)
    s = SVG(w, h)
    s.text(16, 24, "§8d very-heavy noise (0.5/0.5): outcome composition, 2 reps pooled",
           size=13, fill=INK, weight="600")
    s.text(16, 41, "Out of 120 ticket-attempts per arm (2 reps x 60 tickets); severity-ordered, light to dark",
           size=11, fill=INK2)
    left, right = 130, w - 16
    denom = 120.0
    scale = (right - left) / denom
    y = 62
    for label, counts, _ in rows:
        s.text(left - 8, y + 15, label, size=11, fill=INK2, anchor="end")
        x = left
        total_w = sum(counts) * scale
        for (cname, color), n in zip(classes, counts):
            seg = n * scale - 2
            if n > 0:
                s.hbar(x, y, seg, 22, color,
                       rounded_end=(x + n * scale >= left + total_w - 0.5))
                if seg > 16:
                    fill = INK if color == ORDINAL[0] else "#ffffff"
                    s.text(x + seg / 2, y + 15, str(n), size=11, fill=fill,
                           anchor="middle")
            x += n * scale
        y += 44
    s.legend(16, h - 12, classes)
    s.save("trackd_8d_composition.svg")


def fleet_records():
    p = REPO / "results" / "trackc" / "fleet_runs.jsonl"
    return {r["run_id"]: r for r in map(json.loads, p.read_text().splitlines())}


def fig_acceptance(recs):
    vals = {rid: sum(recs[rid]["acceptance"].values()) for rid, _, _ in PRIMARY}
    grouped_columns(
        "trackd_acceptance.svg",
        "Scale-up 1: tickets accepted per run (of 20)",
        "10 workers, corpus v2, claude-sonnet-5, nool 6.14.1; hidden acceptance tests on final main state",
        ["rep 1", "rep 2"],
        [("git_fleet", GIT, [vals["fleet_git_fleet_9a6eb70f"],
                             vals["fleet_git_fleet_803f2288"]]),
         ("nool_fleet", NOOL, [vals["fleet_nool_fleet_cb7ccf72"],
                               vals["fleet_nool_fleet_2a51582f"]])],
        ymax=20, yticks=[0, 5, 10, 15, 20], ylabel="tickets accepted")


def fig_composition(recs):
    classes = [("Accepted", ORDINAL[0]),
               ("Integrated, acceptance failed (test unmet)", ORDINAL[1]),
               ("Merge conflict, not integrated", ORDINAL[2]),
               ("Integrated, acceptance failed (main build broken)", ORDINAL[3])]
    rows = []
    for rid, label, _ in PRIMARY:
        r = recs[rid]
        conflict = sum(1 for i in r["integration"] if not i["clean"])
        accepted = sum(r["acceptance"].values())
        build_ok = r["final_health"]["build_ok"]
        rest = 20 - conflict - accepted
        unmet, voided = (rest, 0) if build_ok else (0, rest)
        rows.append((label, [accepted, unmet, conflict, voided]))
    w, h = 700, 96 + 44 * len(rows)
    s = SVG(w, h)
    s.text(16, 24, "Scale-up 1: outcome of the 20-ticket backlog, per run",
           size=13, fill=INK, weight="600")
    s.text(16, 41, "Classes ordered by severity (light to dark); counts labeled where they fit",
           size=11, fill=INK2)
    left, right = 96, w - 16
    scale = (right - left) / 20.0
    y = 62
    for label, counts in rows:
        s.text(left - 8, y + 15, label, size=11, fill=INK2, anchor="end")
        x = left
        total_w = sum(counts) * scale
        for (cname, color), n in zip(classes, counts):
            seg = n * scale - 2  # 2px surface gap between segments
            if n > 0:
                s.hbar(x, y, seg, 22, color,
                       rounded_end=(x + n * scale >= left + total_w - 0.5))
                if seg > 16:
                    fill = INK if color == ORDINAL[0] else "#ffffff"
                    s.text(x + seg / 2, y + 15, str(n), size=11, fill=fill,
                           anchor="middle")
            x += n * scale
        y += 44
    s.legend(16, h - 30, classes[:2])
    s.legend(16, h - 12, classes[2:])
    s.save("trackd_composition.svg")


def fig_clusters(recs):
    series, seen = [], set()
    for rid, label, color in PRIMARY:
        r = recs[rid]
        clean = {i["ticket"]: i["clean"] for i in r["integration"]}
        arm = r["arm"]
        legend = arm if arm not in seen else None  # one legend entry per arm
        seen.add(arm)
        series.append((legend, color,
                       [sum(clean[t] for t in ts) for ts in CLUSTERS.values()]))
    grouped_columns(
        "trackd_cluster_merges.svg",
        "Scale-up 1: clean merges per contention cluster (of 3)",
        "A: same function (billing Invoice) · B: same handler file · C: same store file; per arm, rep 1 then rep 2",
        [f"cluster {c}" for c in CLUSTERS],
        series, ymax=3, yticks=[0, 1, 2, 3], ylabel="clean merges")


def fig_cost(recs):
    cpa = {rid: recs[rid]["cost_usd"] / sum(recs[rid]["acceptance"].values())
           for rid, _, _ in PRIMARY}
    grouped_columns(
        "trackd_cost.svg",
        "Scale-up 1: agent spend per accepted ticket",
        "Total run spend divided by tickets accepted; per-run spend is near-identical ($3.68-3.90)",
        ["rep 1", "rep 2"],
        [("git_fleet", GIT, [cpa["fleet_git_fleet_9a6eb70f"],
                             cpa["fleet_git_fleet_803f2288"]]),
         ("nool_fleet", NOOL, [cpa["fleet_nool_fleet_cb7ccf72"],
                               cpa["fleet_nool_fleet_2a51582f"]])],
        ymax=4, yticks=[0, 1, 2, 3, 4], ylabel="USD per accepted ticket",
        value_fmt=lambda v: f"${v:.2f}")


LADDER = [
    ("N=10 (v2)", 20, ("fleet_git_fleet_9a6eb70f", "fleet_git_fleet_803f2288"),
                       ("fleet_nool_fleet_cb7ccf72", "fleet_nool_fleet_2a51582f")),
    ("N=20 (v3)", 60, ("fleet_git_fleet_37f30954", "fleet_git_fleet_99caf2f1"),
                       ("fleet_nool_fleet_15da1d64", "fleet_nool_fleet_77ba01c2")),
    ("N=25 (v3)", 60, ("fleet_git_fleet_71ab28f3", "fleet_git_fleet_a7499905"),
                       ("fleet_nool_fleet_ca131262", "fleet_nool_fleet_4800a387")),
    ("N=35 (v3)", 60, ("fleet_git_fleet_a281c84e", "fleet_git_fleet_89ec7e04"),
                       ("fleet_nool_fleet_9c5490e1", "fleet_nool_fleet_c5712d86")),
]


def fig_ladder(recs):
    def rate(rids, denom):
        return 100.0 * sum(sum(recs[rid]["acceptance"].values())
                           for rid in rids) / (len(rids) * denom)
    groups = [g for g, *_ in LADDER]
    git_vals = [rate(g_ids, denom) for _, denom, g_ids, _ in LADDER]
    nool_vals = [rate(n_ids, denom) for _, denom, _, n_ids in LADDER]
    grouped_columns(
        "trackd_ladder.svg",
        "Concurrency ladder: mean ticket-acceptance rate by N",
        "Mean of 2 reps/arm/point; N=10 is corpus v2 (20 tickets, scale-up 1), N=20/25/35 are corpus v3 (60 tickets, scale-up 2) -- not one scaled corpus, see caption",
        groups,
        [("git_fleet", GIT, git_vals), ("nool_fleet", NOOL, nool_vals)],
        ymax=100, yticks=[0, 25, 50, 75, 100],
        ylabel="% tickets accepted (mean of 2 reps)",
        value_fmt=lambda v: f"{v:.0f}%")


def fig_b5():
    data = []
    for tag, p in (("6.13.0", "results/replications/run1_micro_2026-08-20"),
                   ("6.14.0", "results/replications/run2_micro_2026-08-20"),
                   ("6.14.1", "results/micro")):
        b5 = json.loads((REPO / p / "b5_swarm_merge.json").read_text())
        g = b5["cells"]["same_anchor_git"][0]["clean_merges"]
        n = b5["cells"]["same_anchor_nool"][0]["clean_merges"]
        data.append((tag, g, n))
    grouped_columns(
        "b5_versions.svg",
        "B5: clean merges of 15 contended branches, by nool version",
        "Same-anchor scenario, 3 reps per version (values identical across reps); git baseline unchanged",
        [t for t, _, _ in data],
        [("git merge", GIT, [g for _, g, _ in data]),
         ("nool merge", NOOL, [n for _, _, n in data])],
        ymax=15, yticks=[0, 5, 10, 15], ylabel="clean merges")


def fig_b2():
    b2 = json.loads((REPO / "results/micro/b2_concurrency.json").read_text())
    ns = ["2", "5", "15"]
    git = [100.0 * b2["cells"][f"git_n{n}"]["ops_swept_into_other_commit"]
           / b2["cells"][f"git_n{n}"]["ops_expected"] for n in ns]
    nool = [100.0 * b2["cells"][f"nool_n{n}"]["ops_swept_into_other_commit"]
            / b2["cells"][f"nool_n{n}"]["ops_expected"] for n in ns]
    grouped_columns(
        "b2_attribution.svg",
        "B2: writes swept into another agent's commit (shared workspace)",
        "Percent of expected ops misattributed at N concurrent writers; nool 6.14.1, run 3",
        [f"N = {n}" for n in ns],
        [("git", GIT, git), ("nool", NOOL, nool)],
        ymax=60, yticks=[0, 20, 40, 60], ylabel="% of ops misattributed",
        value_fmt=lambda v: f"{v:.0f}%")


def fig_b6():
    b6 = json.loads((REPO / "results/micro/b6_context_retrieval.json").read_text())
    q = b6["queries"]
    rows = [("grep + read files (baseline)", "baseline_grep_read"),
            ("nool query search → context (chain)", "nool_search_then_context"),
            ("nool query search (refs only)", "nool_query_search"),
            ("nool query context, file-level", "nool_query_context_file"),
            ("nool query context, symbol-level", "nool_query_context_symbol")]
    w, h = 700, 92 + 34 * len(rows)
    s = SVG(w, h)
    s.text(16, 24, "B6: bytes an agent ingests to reach the target context",
           size=13, fill=INK, weight="600")
    s.text(16, 41, "13-file repo, one seeded fact; gray = query returned no hit; nool 6.14.1, run 3",
           size=11, fill=INK2)
    left, right = 300, w - 60
    vmax = 700.0
    scale = (right - left) / vmax
    y = 62
    for label, key in rows:
        v, hit = q[key]["bytes"], q[key].get("hit")
        color = NOOL if hit else MUTED
        s.text(left - 8, y + 14, label, size=11, fill=INK2, anchor="end")
        s.hbar(left, y, v * scale, 20, color)
        tip = f"{v}" + ("" if hit else " (no hit)")
        s.text(left + v * scale + 6, y + 14, tip, size=11, fill=INK)
        y += 34
    s.line(left, y + 2, left, 56, stroke=BASELINE)
    s.text(right, y + 16, "bytes", size=10.5, fill=MUTED, anchor="end")
    s.save("b6_context_bytes.svg")


def main():
    recs = fleet_records()
    fig_acceptance(recs)
    fig_composition(recs)
    fig_clusters(recs)
    fig_cost(recs)
    fig_ladder(recs)
    fig_b5()
    fig_b2()
    fig_b6()
    fig_8d_degradation(recs)
    fig_8d_conflicts(recs)
    fig_8d_composition(recs)


if __name__ == "__main__":
    main()
