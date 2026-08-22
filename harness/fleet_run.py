#!/usr/bin/env python3
"""Track D — Fleet Operations Benchmark (pre-registered in the design spec §8a;
arm-decomposition study pre-registered §8c, 2026-08-22).

N real agents process a ticket backlog against one shared codebase. Five arms
decompose dispatch policy, integration policy, and coordination source:

  git_fleet       : uncoordinated baseline — every ticket dispatched in
                    parallel; integration is a sequential blind `git merge`
                    queue in ticket order (conflicts aborted, never resolved).
  git_gated_queue : same parallel dispatch, but the merge queue is CI-gated —
                    a merge whose post-merge build or smoke tests fail is
                    reverted and recorded as queue-rejected (models the
                    standard test-gated merge queue).
  git_scheduled   : footprint-gated dispatch (harness scheduler over the
                    corpus's declared footprints — identical logic to
                    nool_fleet's scheduler) with plain `git merge` on
                    completion and no nool anywhere. Ablation arm: isolates
                    the scheduling policy from the product.
  nool_fleet      : footprint-gated dispatch by the SAME harness scheduler;
                    integration is `nool merge` on completion. NOTE (audit
                    2026-08-22): the hold/admit decision here is computed by
                    the harness from declared footprints; `nool announce` /
                    `nool discover conflicts` are invoked at admission and
                    recorded, but their verdicts are advisory-only and do not
                    gate. Kept unchanged for continuity with collected data.
  nool_gated      : dispatch gated by nool itself — admission requires a
                    successful `nool announce intent` over the ticket's
                    footprint (nool refuses overlapping announcements with a
                    coordination-conflict error); the lease is released after
                    integration. Integration is `nool merge` on completion.

Identical prompts, model, worker count, and worktree isolation in every arm.
Main-branch health (build + smoke tests) is recorded after every merge;
ticket acceptance is scored against hidden per-ticket tests at the end.
Before every run the starter tree is hashed and checked against the pinned
corpus hash (tasks/fleet_service/STARTER_SHA256).
"""

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapters import claude as claude_adapter  # noqa: E402
from adapters import opencode as opencode_adapter  # noqa: E402
from run_experiment import ENV, RESULTS, TRANSCRIPTS, sh  # noqa: E402

ADAPTERS = {"claude": claude_adapter, "opencode": opencode_adapter}

# Fail-fast guard against provider-limit contamination (incidents of
# 2026-08-21, 2026-08-22, 2026-08-23): a batch that keeps running after the
# account hits its usage limit produces walls of instant-rejection agents
# that look like arm outcomes. Detection is transcript-based (authoritative
# 429/rate_limit markers), so it works for any adapter including free-tier
# ones whose cost_usd is legitimately 0.
_RATE_LIMIT_MARKERS = (
    '"api_error_status": 429',
    '"error": "rate_limit"',
    'rate_limit_event',
    'session limit',
)


class RateLimitAbort(RuntimeError):
    pass


_ABORT = threading.Event()


def transcript_rate_limited(tpath):
    try:
        with open(tpath, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65536))
            tail = f.read().decode("utf-8", errors="replace").lower()
    except OSError:
        return False
    return any(m.lower() in tail for m in _RATE_LIMIT_MARKERS)


REPO = Path(__file__).resolve().parent.parent
TASK = REPO / "tasks" / "fleet_service"
STARTER_PIN = TASK / "STARTER_SHA256"
GOV = REPO / "harness" / "governance"

# Symmetric secret-scanning gate (industry CI practice, gitleaks-style).
# Applied identically to EVERY arm at integration: a hit is recorded in all
# arms and additionally rejects the merge in CI-gated arms. Patterns are
# deliberately conservative (known credential formats only) to keep the
# false-positive rate near zero for this corpus.
SECRET_PATTERNS = [
    ("aws_access_key_id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("github_classic_pat", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("openai_api_key", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private_key_header", re.compile(
        r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
]


def secret_scan(ws, pre_rev):
    """Scan everything a merge is about to add (diff pre..working tree)."""
    _, diff = sh(["git", "diff", pre_rev, "--"], ws)
    hits = []
    for label, pat in SECRET_PATTERNS:
        if pat.search(diff):
            hits.append(label)
    return {"clean": not hits, "hits": hits}


def evolution_summary(rec, tickets, ws):
    """Safe-software-evolution metrics computed from run records + final
    main. All values are derived from recorded observations; nothing here
    re-runs agents or scores tests (that is rec['acceptance']).

    attribution_purity: for each accepted ticket, the fraction of its
    declared footprint files whose last non-merge commit on main belongs
    to that ticket (subject carries the ticket id). 1.0 means every file
    the ticket owned was landed by that ticket's own work; low values mean
    another writer's commit swept the file in — an attribution defect.
    """
    integ = {i["ticket"]: i for i in rec["integration"]}
    accepted = [t["id"] for t in tickets if rec["acceptance"].get(t["id"])]
    conflicts = sum(1 for i in rec["integration"] if not i["clean"])
    merge_errors = sum(1 for i in rec["integration"]
                       if i["clean"] and i["exit_code"] != 0)
    queue_rejected = sum(1 for i in rec["integration"] if i.get("queue_rejected"))
    broken_main = sum(1 for i in rec["integration"]
                      if i.get("post_merge_health")
                      and not (i["post_merge_health"]["build_ok"]
                               and i["post_merge_health"]["smoke_ok"]))
    wasted = {tid: rec["agents"].get(tid, {}) for tid in
              [t["id"] for t in tickets if not rec["acceptance"].get(t["id"])]}
    purity = {}
    by_id = {t["id"]: t for t in tickets}
    for tid in accepted:
        files = by_id[tid].get("footprint") or []
        ok = 0
        for f in files:
            _, subs = sh(["git", "log", "--format=%s", "--non-merges",
                          "--", f], ws)
            lines = [l for l in subs.splitlines() if l.strip()]
            if lines and all(tid in l or not any(
                    t2["id"] in l for t2 in tickets) for l in lines):
                ok += 1
        purity[tid] = round(ok / len(files), 3) if files else None
    gov = {"announcements": sum(len(v) for v in rec.get("gating", {}).values()),
           "releases_recorded": len(rec.get("releases", {}))}
    return {
        "accepted": len(accepted),
        "conflicts": conflicts,
        "merge_errors": merge_errors,
        "queue_rejected": queue_rejected,
        "broken_main_merges": broken_main,
        "secret_hits": sorted({h for i in rec["integration"]
                               if i.get("secret_scan")
                               for h in i["secret_scan"]["hits"]}),
        "wasted_cost_usd": round(sum((a.get("cost_usd") or 0)
                                     for a in wasted.values()), 4),
        "wasted_wall_ms": round(sum((a.get("wall_ms") or 0)
                                    for a in wasted.values()), 1),
        "attribution_purity": purity,
        "mean_attribution_purity": round(sum(v for v in purity.values()
                                             if v is not None)
                                         / len(purity), 3) if purity else None,
        "governance_events": gov,
    }

ARMS = {
    "git_fleet":       {"dispatch": "parallel",  "ci_gate": False, "merge": "git",  "nool_ws": False},
    "git_gated_queue": {"dispatch": "parallel",  "ci_gate": True,  "merge": "git",  "nool_ws": False},
    "git_scheduled":   {"dispatch": "footprint", "ci_gate": False, "merge": "git",  "nool_ws": False},
    "nool_fleet":      {"dispatch": "footprint", "ci_gate": False, "merge": "nool", "nool_ws": True},
    "nool_gated":      {"dispatch": "lease",     "ci_gate": False, "merge": "nool", "nool_ws": True},
}

# Covers the agent timeout (600 s) plus integration; a leaked lease expires
# on its own after this rather than blocking the run forever.
LEASE_DURATION_MS = 900000

PROMPT = """You are working in a Go service repository (module bench/fleetsvc).
Implement the following ticket. Modify only what the ticket requires.

Ticket {tid} — {title}

{spec}

Verify with `go build ./...` and `go test ./...` (the existing tests must
stay green). Land your work with the version-control workflow available in
this repository, then stop.
"""


def starter_sha():
    """Deterministic content hash of the starter tree (paths + bytes)."""
    h = hashlib.sha256()
    root = TASK / "starter"
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    return h.hexdigest()


def check_starter_pin(allow_unpinned):
    sha = starter_sha()
    if STARTER_PIN.exists():
        pinned = STARTER_PIN.read_text().split()[0]
        if sha != pinned and not allow_unpinned:
            raise RuntimeError(
                f"starter tree hash {sha} != pinned {pinned} "
                f"({STARTER_PIN}); corpus may be contaminated — diff "
                "tasks/fleet_service/starter against the pre-registration "
                "commit, or pass --allow-unpinned-starter to override.")
    elif not allow_unpinned:
        raise RuntimeError(f"{STARTER_PIN} missing; refusing to run unpinned.")
    return sha


def setup_ws(arm, parent):
    """Workspace contract.

    Every arm starts from a fresh copy of the pinned starter as a real git
    repo (`git init` + base commit). Both arms then receive the IDENTICAL
    industry-standard governance documentation (ci.yml required checks,
    CODEOWNERS, POLICY.md, .pre-commit-config.yaml) — the rules are held
    constant; only the enforcement substrate differs. Nool arms
    additionally `nool init` on top of that repo, apply the governed
    profile (harness/governance/nool_governed.toml), and hard-fail unless
    `nool verify --all` accepts the profile.
    """
    ws = Path(parent) / "main_ws"
    shutil.copytree(TASK / "starter", ws)
    if (ws / ".nool").exists():
        raise RuntimeError("starter corpus must not ship a .nool ledger")
    for cmd in (["git", "init", "-q", "-b", "main"],
                ["git", "config", "user.email", "bench@nool-benchmarks.local"],
                ["git", "config", "user.name", "Bench"],
                ["git", "add", "-A"], ["git", "commit", "-qm", "base service"]):
        sh(cmd, ws, check=True)
    # Identical policy documentation for every arm (constant across arms).
    gh = ws / ".github" / "workflows"
    gh.mkdir(parents=True)
    shutil.copy(GOV / "industry_git" / "ci.yml", gh / "ci.yml")
    shutil.copy(GOV / "industry_git" / "CODEOWNERS", ws / "CODEOWNERS")
    shutil.copy(GOV / "industry_git" / "POLICY.md", ws / "POLICY.md")
    shutil.copy(GOV / "industry_git" / ".pre-commit-config.yaml",
                ws / ".pre-commit-config.yaml")
    profile_sha = None
    if ARMS[arm]["nool_ws"]:
        code, out = sh(["nool", "init"], ws, timeout=120)
        if code != 0:
            raise RuntimeError(out)
        prof = GOV / "nool_governed.toml"
        shutil.copy(prof, ws / "nool.toml")
        profile_sha = hashlib.sha256(prof.read_bytes()).hexdigest()
        c, s = sh(["nool", "status", "--json"], ws, timeout=120)
        if c != 0:
            raise RuntimeError(f"nool ledger not live after init:\n{s}")
        v, vout = sh(["nool", "verify", "--all", "--compact"], ws, timeout=300)
        if v != 0:
            raise RuntimeError(f"governance profile failed verify:\n{vout}")
        sh(["git", "add", "-A"], ws)
        sh(["git", "commit", "-qm", "governed substrate"], ws)
    else:
        # The git control arm must have no coordination substrate at all.
        # Deliberately NOT probed with `nool status`: invoking the CLI can
        # auto-create a bare .nool ledger as a side effect, which would
        # contaminate the arm we are asserting is clean.
        if (ws / ".nool").exists():
            raise RuntimeError("unexpected .nool ledger in git control arm")
    return ws, profile_sha


def health(ws):
    b, _ = sh(["go", "build", "./..."], ws, timeout=120)
    t, _ = sh(["go", "test", "./..."], ws, timeout=180)
    return {"build_ok": b == 0, "smoke_ok": t == 0}


# Concurrent `git worktree add` on one repo races on .git/worktrees admin
# metadata (observed: "failed to read .git/worktrees/wt_t8/commondir" killing
# a 20-agent run). Creation is ~100ms and not part of the measured treatment,
# so serialize it; agent work itself stays fully concurrent.
_WORKTREE_ADD_LOCK = threading.Lock()

# N=25 (scale-up 2, design spec) reproducibly exhausted operator-machine RAM
# within ~9s: ThreadPoolExecutor(max_workers=25) launches that many Claude
# Code CLI subprocesses in one instant burst. Throttling launch cadence
# (not the treatment — applies identically to every arm, since every arm
# routes through this function) spreads the ramp-up instead of spiking it.
_LAUNCH_LOCK = threading.Lock()
_LAST_LAUNCH = [0.0]
LAUNCH_STAGGER_S = 1.5


def _throttle_launch():
    with _LAUNCH_LOCK:
        wait = _LAST_LAUNCH[0] + LAUNCH_STAGGER_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _LAST_LAUNCH[0] = time.monotonic()


def agent_env(arm):
    """Agent-visible environment. Control-arm agents must not see the
    treatment substrate on PATH: 'the version-control workflow available in
    this repository' is git-only there, and a nool binary in reach invites
    off-protocol auto-init inside untracked worktrees (observed 2026-08-22).
    Nool arms keep the full PATH."""
    env = dict(ENV)
    if not ARMS[arm]["nool_ws"] and env.get("PATH"):
        # Drop every PATH entry that would put a `nool` binary in reach.
        parts = [p for p in env["PATH"].split(os.pathsep)
                 if p and not (Path(p) / "nool").exists()]
        env["PATH"] = os.pathsep.join(parts)
    return env


def agent_ticket(ws, parent, ticket, model, run_id, adapter, arm):
    wt = Path(parent) / f"wt_{ticket['id']}"
    with _WORKTREE_ADD_LOCK:
        sh(["git", "worktree", "add", "-q", "-b", f"ticket_{ticket['id']}",
            str(wt), "main"], ws, check=True)
    prompt = PROMPT.format(tid=ticket["id"], title=ticket["title"],
                           spec=ticket["spec"])
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    tpath = TRANSCRIPTS / f"{run_id}_{ticket['id']}.jsonl"
    _throttle_launch()
    res = adapter.run(wt, prompt, model, max_turns=30, timeout_s=600,
                      transcript_path=tpath, env=agent_env(arm))
    if _ABORT.is_set() or transcript_rate_limited(tpath):
        # Stop the batch before it writes a corrupted record: a 429 wall is
        # provider state, not an arm outcome (see invalidated_2026-08-2*
        # NOTEs). The partial record is intentionally NOT appended.
        _ABORT.set()
        raise RateLimitAbort(
            f"{ticket['id']}: rate-limit signature in transcript "
            f"(or batch already aborted) — fix account headroom and rerun; "
            f"no fleet_runs.jsonl record written for this run")
    sh(["git", "add", "-A"], wt)
    # VCS-internal state is never authored work: keep auto-created nool
    # ledgers out of ticket branches so they cannot collide at merge time.
    sh(["git", "reset", "-q", "--", ".nool"], wt)
    sh(["git", "commit", "-qm", f"{ticket['id']} leftovers"], wt)
    print(f"[{run_id}] {ticket['id']} agent done "
          f"{res['wall_ms']/1000:.0f}s turns={res.get('num_turns')} "
          f"tools={res.get('tool_calls')} timed_out={res['timed_out']}",
          flush=True)
    return {**res, "transcript": str(tpath.relative_to(REPO))}


def integrate(ws, arm, ticket, run_id=""):
    branch = f"ticket_{ticket['id']}"
    _, pre = sh(["git", "rev-parse", "HEAD"], ws)
    pre = pre.strip()
    if ARMS[arm]["merge"] == "nool":
        code, out = sh(["nool", "merge", branch, "--compact"], ws, timeout=300)
    else:
        code, out = sh(["git", "merge", "-q", "--no-edit", branch], ws, timeout=300)
    merge_tail = out.strip().splitlines()[-8:]
    _, status = sh(["git", "status", "--porcelain"], ws)
    conflicted = any(l[:2] in ("UU", "AA", "DD", "AU", "UA", "DU", "UD")
                     for l in status.splitlines())
    if conflicted:
        sh(["git", "merge", "--abort"], ws)
        print(f"[{run_id}] {ticket['id']} merge CONFLICT (aborted)", flush=True)
        return {"ticket": ticket["id"], "clean": False, "exit_code": code,
                "queue_rejected": False, "post_merge_health": None,
                "secret_scan": None, "merge_tail": merge_tail}
    scan = secret_scan(ws, pre)
    h = health(ws)
    rejected = ARMS[arm]["ci_gate"] and not (
        h["build_ok"] and h["smoke_ok"] and scan["clean"])
    if rejected:
        # CI-gated queue: a red merge does not land. Reset to the exact
        # pre-merge commit (not ORIG_HEAD, which is stale on no-op merges).
        sh(["git", "reset", "--hard", pre], ws, check=True)
    tag = ("QUEUE-REJECTED" if rejected else
           "landed" if code == 0 else f"MERGE-ERROR exit={code}")
    if not scan["clean"]:
        tag += f" SECRETS={','.join(scan['hits'])}"
    print(f"[{run_id}] {ticket['id']} merge {tag} "
          f"build={'ok' if h['build_ok'] else 'FAIL'} "
          f"smoke={'ok' if h['smoke_ok'] else 'FAIL'} "
          f"secrets={'clean' if scan['clean'] else 'HIT'}", flush=True)
    return {"ticket": ticket["id"], "clean": True, "exit_code": code,
            "queue_rejected": rejected,
            "post_merge_health": h, "secret_scan": scan,
            "merge_tail": merge_tail}
    return {"ticket": ticket["id"], "clean": True, "exit_code": code,
            "queue_rejected": rejected, "post_merge_health": h,
            "merge_tail": merge_tail}


def score(ws, tickets):
    out = {}
    for t in tickets:
        dst = ws / "accept" / t["id"]
        shutil.copytree(TASK / "accept" / t["id"], dst)
        code, _ = sh(["go", "test", f"./accept/{t['id']}/"], ws, timeout=120)
        out[t["id"]] = code == 0
        shutil.rmtree(ws / "accept")
    return out


def nool_gate(ws, ticket):
    """Advisory-only record of nool's announce/discover output at admission.

    Audit note (2026-08-22): these verdicts never gated dispatch, and
    `discover conflicts` reports no conflicts even against an active
    overlapping lease (the refusal lives in `announce intent`, exit 3).
    Kept so nool_fleet records stay schema-identical to collected data.

    Isolation fix (2026-08-22, post-audit): the announcement now carries the
    ticket's agent id and `discover conflicts` passes `--as-agent`, without
    which several agents sharing one machine identity make discover a silent
    self-match no-op (per the CLI's own help). The lease is released after
    integration so announcements cannot accumulate across runs (TTL is an
    hour; leaked leases would bleed state into subsequent runs).
    """
    aid = f"agent_{ticket['id']}"
    fp = ",".join(ticket["footprint"])
    a_code, a_out = sh(["nool", "announce", "intent", "--intent",
                        f"ticket {ticket['id']}: {ticket['title']}",
                        "--target-nodes", fp, "--agent-id", aid,
                        "--estimated-duration-ms", str(LEASE_DURATION_MS),
                        "--compact"], ws, timeout=120)
    d_code, d_out = sh(["nool", "discover", "conflicts",
                        *ticket["footprint"], "--as-agent", aid,
                        "--compact"], ws, timeout=120)
    return {"announce_exit": a_code, "discover_exit": d_code,
            "discover_tail": d_out.strip().splitlines()[-2:],
            "agent_id": aid}


def release_lease(ws, ticket, gate):
    """Release the admission lease (best effort) so nothing outlives the run.
    Each ticket announces under its own agent id, so --all scoped to that
    id releases exactly this ticket's lease."""
    aid = (gate or {}).get("agent_id")
    rel = ["nool", "announce", "release", "--all"]
    if aid:
        rel += ["--agent-id", aid]
    rel += ["--compact"]
    c, o = sh(rel, ws, timeout=120)
    return {"exit": c, "tail": o.strip().splitlines()[-1:]}


def preflight_isolation():
    """Refuse to run on a machine with leftover coordination state: stale
    daemons race the benchmark's nool clients, and live announcements/leases
    from earlier sessions bleed into dispatch records."""
    import subprocess as sp
    pids = sp.run(["pgrep", "-f", "nool-daemon"], capture_output=True,
                  text=True).stdout.split()
    if pids:
        raise RuntimeError(
            f"{len(pids)} nool-daemon process(es) already running "
            f"({', '.join(pids[:5])}...). Kill them before benchmarking: "
            "`pkill -f nool-daemon`. Stale daemons were implicated in the "
            "2026-08-22 merge failures.")
    return {"daemon_pids": []}


def run_parallel(rec, ws, parent, tickets, model, run_id, n_workers, arm,
                 adapter):
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(max_workers=n_workers) as ex:
        futs = {ex.submit(agent_ticket, ws, parent, t, model, run_id,
                          adapter, arm): t
                for t in tickets}
        for f in futs:
            rec["agents"][futs[f]["id"]] = f.result()
            # f.result() re-raises RateLimitAbort from agent_ticket; the
            # remaining futures observe _ABORT after their current agent
            # and abort the same way on collection below.
    for t in tickets:  # sequential merge queue, ticket order
        rec["integration"].append(integrate(ws, arm, t, run_id))


def run_footprint_gated(rec, ws, parent, tickets, model, run_id, n_workers,
                        arm, adapter):
    """Harness scheduler: hold a ticket while any in-flight ticket's declared
    footprint intersects its own. The oracle-footprint policy arm."""
    lock = threading.Lock()
    inflight = {}          # ticket id -> footprint set
    done = set()

    def worker(t, gate):
        try:
            res = agent_ticket(ws, parent, t, model, run_id, adapter, arm)
        except RateLimitAbort:
            return          # _ABORT is set; the batch aborts after join
        with lock:
            rec["agents"][t["id"]] = res
            rec["integration"].append(integrate(ws, arm, t, run_id))
            if gate is not None:
                # Release the admission lease immediately: leaked leases
                # (TTL up to an hour) would bleed into any subsequent run.
                rec["releases"][t["id"]] = release_lease(ws, t, gate)
            del inflight[t["id"]]
            done.add(t["id"])

    threads = []
    pending = list(tickets)
    while pending or inflight:
        if _ABORT.is_set() and not inflight:
            break
        with lock:
            busy = set().union(*inflight.values()) if inflight else set()
            ready = []
            for t in pending:
                if set(t["footprint"]) & busy:
                    continue
                if len(inflight) + len(ready) >= n_workers:
                    break
                ready.append(t)
                # Tickets admitted in the same batch must gate each other
                # too — busy alone let the whole first wave dispatch from
                # one base, racing cluster members (observed t9 vs t10,
                # t12 vs t13 same-batch conflicts).
                busy |= set(t["footprint"])
            for t in ready:
                if arm == "nool_fleet":
                    gate = nool_gate(ws, t)
                    rec["gating"].setdefault(t["id"], []).append(gate)
                else:
                    gate = None
                inflight[t["id"]] = set(t["footprint"])
                pending.remove(t)
                print(f"[{run_id}] {t['id']} dispatched "
                      f"({len(inflight)}/{n_workers} in flight, "
                      f"{len(pending)} queued)", flush=True)
                th = threading.Thread(target=worker, args=(t, gate))
                th.start()
                threads.append(th)
        time.sleep(2)
    for th in threads:
        th.join()
    if _ABORT.is_set():
        raise RateLimitAbort("batch aborted: provider rate limit detected")


def run_lease_gated(rec, ws, parent, tickets, model, run_id, n_workers, arm,
                    adapter):
    """nool-native scheduler: admission requires `nool announce intent` to
    succeed (nool refuses overlapping leases, exit 3); the lease is released
    after integration. The harness contributes only worker-slot capacity."""
    lock = threading.Lock()
    inflight = {}            # ticket id -> announcement id (or None)
    release_epoch = [0]
    last_refused = {}        # ticket id -> epoch of last refused announce

    def worker(t, aid):
        try:
            res = agent_ticket(ws, parent, t, model, run_id, adapter, arm)
        except RateLimitAbort:
            return          # _ABORT is set; the batch aborts after join
        with lock:
            rec["agents"][t["id"]] = res
            rec["integration"].append(integrate(ws, arm, t, run_id))
            rel = ["nool", "announce", "release"]
            rel += [aid] if aid else ["--all"]
            rel += ["--agent-id", f"agent_{t['id']}", "--compact"]
            r_code, r_out = sh(rel, ws, timeout=120)
            rec["releases"][t["id"]] = {"exit": r_code,
                                        "tail": r_out.strip().splitlines()[-1:]}
            release_epoch[0] += 1
            del inflight[t["id"]]

    threads = []
    pending = list(tickets)
    while pending or inflight:
        if _ABORT.is_set() and not inflight:
            break
        with lock:
            epoch = release_epoch[0]
            for t in list(pending):
                if len(inflight) >= n_workers:
                    break
                # A refused ticket re-attempts only after some lease was
                # released (or when nothing is in flight — covers lease
                # expiry after a failed release).
                if last_refused.get(t["id"]) == epoch and inflight:
                    continue
                fp = ",".join(t["footprint"])
                code, out = sh(["nool", "announce", "intent", "--intent",
                                f"ticket {t['id']}: {t['title']}",
                                "--target-nodes", fp,
                                "--agent-id", f"agent_{t['id']}",
                                "--estimated-duration-ms", str(LEASE_DURATION_MS),
                                "--compact"], ws, timeout=120)
                rec["gating"].setdefault(t["id"], []).append(
                    {"announce_exit": code,
                     "tail": out.strip().splitlines()[-1:]})
                if code == 0:
                    m = re.search(r"Announcement ID: (\S+)", out)
                    aid = m.group(1) if m else None
                    inflight[t["id"]] = aid
                    pending.remove(t)
                    print(f"[{run_id}] {t['id']} leased "
                          f"({len(inflight)}/{n_workers} in flight, "
                          f"{len(pending)} queued)", flush=True)
                    th = threading.Thread(target=worker, args=(t, aid))
                    th.start()
                    threads.append(th)
                else:
                    last_refused[t["id"]] = epoch
        time.sleep(2)
    for th in threads:
        th.join()
    if _ABORT.is_set():
        raise RateLimitAbort("batch aborted: provider rate limit detected")


def run_fleet(arm, model, n_workers, tickets_file="tickets.json",
              allow_unpinned=False, harness="claude", limit=None,
              seed=None):
    if arm not in ARMS:
        raise SystemExit(f"unknown arm {arm!r}; valid: {', '.join(ARMS)}")
    adapter = ADAPTERS[harness]
    sha = check_starter_pin(allow_unpinned)
    run_id = f"fleet_{arm}_{uuid.uuid4().hex[:8]}"
    print(f"[{run_id}] starting arm={arm} harness={harness} model={model} "
          f"workers={n_workers}", flush=True)
    corpus = json.loads((TASK / tickets_file).read_text())
    tickets = corpus["tickets"]
    if limit:
        tickets = tickets[:limit]
        print(f"[{run_id}] NOTE pipeline-validation slice: first {limit} "
              "tickets only; do not pool with full-corpus results", flush=True)
    parent = tempfile.mkdtemp(prefix=run_id + "_")
    ws, gov_profile_sha = setup_ws(arm, parent)
    rng = random.Random(seed)
    order = list(range(len(tickets)))
    rng.shuffle(order)
    tickets = [tickets[i] for i in order]
    print(f"[{run_id}] ticket order shuffled with seed={seed}", flush=True)
    ver = lambda c: subprocess.run(c, capture_output=True, text=True,
                                   timeout=15).stdout.strip().splitlines()[0]
    rec = {"run_id": run_id, "arm": arm, "arm_policy": ARMS[arm],
           "harness": harness, "model": model, "n_workers": n_workers,
           "corpus": corpus.get("corpus", "v1"), "tickets_file": tickets_file,
           "ticket_limit": limit,
           "shuffle_seed": seed,
           "governance_profile_sha": gov_profile_sha,
           "starter_sha": sha,
           "started_utc": datetime.now(timezone.utc).isoformat(),
           "preflight": adapter.preflight(),
           "isolation": preflight_isolation(),
           "nool_version": ver(["nool", "--version"]),
           "git_version": ver(["git", "--version"]),
           "go_version": ver(["go", "version"]),
           "agents": {}, "integration": [], "gating": {}, "releases": {}}
    t0 = time.monotonic()
    _ABORT.clear()
    try:
        dispatch = {"parallel": run_parallel,
                    "footprint": run_footprint_gated,
                    "lease": run_lease_gated}[ARMS[arm]["dispatch"]]
        dispatch(rec, ws, parent, tickets, model, run_id, n_workers, arm,
                 adapter)

        rec["wall_ms"] = round((time.monotonic() - t0) * 1000.0, 1)
        rec["acceptance"] = score(ws, tickets)
        # Scoring-time corpus-artifact flag (the t21 class): a ticket whose
        # hidden test passes although its work never landed was satisfied by
        # a neighbor's change. Detected here so it is part of the record,
        # not just post-hoc analysis (spec §8c negative-validation limit).
        landed = {i["ticket"] for i in rec["integration"]
                  if i["clean"] and not i.get("queue_rejected")}
        accepted = {t for t, v in rec["acceptance"].items() if v}
        suspect = sorted(accepted - landed)
        if suspect:
            rec["acceptance_artifact_suspect"] = suspect
            print(f"[{run_id}] WARNING accepted-without-landing "
                  f"(corpus artifact class): {','.join(suspect)}", flush=True)
        rec["final_health"] = health(ws)
        _, glog = sh(["git", "log", "--oneline"], ws)
        rec["git_commits_on_main"] = len(glog.splitlines())
        if ARMS[arm]["nool_ws"]:
            code, nlog = sh(["nool", "log", "--json"], ws)
            try:
                rec["nool_knots"] = len(json.loads(nlog))
            except Exception:
                rec["nool_knots"] = None
        rec["cost_usd"] = round(sum((a.get("cost_usd") or 0)
                                    for a in rec["agents"].values()), 4)
        rec["evolution"] = evolution_summary(rec, tickets, ws)
        rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
    finally:
        # Crash-safe: the throwaway workspace must never outlive the run
        # (leaked worktrees re-register with nool/git state on later runs).
        shutil.rmtree(parent, ignore_errors=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "fleet_runs.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    passed = sum(1 for v in rec["acceptance"].values() if v)
    print(f"[{run_id}] accepted {passed}/{len(tickets)} "
          f"wall={rec['wall_ms']/1000:.0f}s cost=${rec['cost_usd']}", flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--harness", default="claude", choices=list(ADAPTERS))
    ap.add_argument("--arms", default="git_fleet,nool_fleet",
                    help=f"comma list from: {', '.join(ARMS)}")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--tickets", default="tickets.json")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None,
                    help="use only the first K tickets (pipeline validation "
                         "runs; records are marked and must not be pooled "
                         "with full-corpus results)")
    ap.add_argument("--seed", type=int, default=None,
                    help="seed for per-run ticket-order shuffle (recorded "
                         "in provenance; random if omitted)")
    ap.add_argument("--allow-unpinned-starter", action="store_true",
                    help="run even if the starter tree hash does not match "
                         "tasks/fleet_service/STARTER_SHA256")
    args = ap.parse_args()
    for _ in range(args.reps):
        for arm in args.arms.split(","):
            run_fleet(arm, args.model, args.workers, args.tickets,
                      allow_unpinned=args.allow_unpinned_starter,
                      harness=args.harness, limit=args.limit,
                      seed=args.seed)


if __name__ == "__main__":
    main()
