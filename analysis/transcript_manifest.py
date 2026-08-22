#!/usr/bin/env python3
"""Integrity manifest for the gitignored raw transcripts.

Raw LLM transcripts under results/trackc/transcripts/ are too large to
commit, but "trust us, we have them" is not provenance. This script hashes
every transcript (SHA-256 + size) into a committed manifest
(results/trackc/transcripts_manifest.jsonl) so a third party who receives
the archive can verify it, and so the committed run records can be audited
against what actually exists on disk.

Modes:
  write  (re)build the manifest from what is on disk
  check  verify disk against the committed manifest; report missing,
         modified, and extra files; also report transcripts referenced by
         committed run records but absent from both.

Usage:
  python3 analysis/transcript_manifest.py write
  python3 analysis/transcript_manifest.py check
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRANSCRIPTS = REPO / "results" / "trackc" / "transcripts"
MANIFEST = REPO / "results" / "trackc" / "transcripts_manifest.jsonl"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def referenced_transcripts():
    refs = set()
    for name in ("runs.jsonl", "fleet_runs.jsonl"):
        p = REPO / "results" / "trackc" / name
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            agents = r.get("agents")
            if isinstance(agents, dict):
                agents = list(agents.values())
            for a in agents or []:
                t = a.get("transcript")
                if t:
                    refs.add(t)
    return refs


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "write":
        files = sorted(TRANSCRIPTS.rglob("*.jsonl"))
        with open(MANIFEST, "w") as f:
            for p in files:
                rel = str(p.relative_to(REPO))
                f.write(json.dumps({"path": rel, "bytes": p.stat().st_size,
                                    "sha256": sha256(p)}) + "\n")
        print(f"wrote {len(files)} entries to {MANIFEST.relative_to(REPO)}")
        return
    if mode != "check":
        sys.exit(f"unknown mode: {mode}")

    if not MANIFEST.exists():
        sys.exit("no manifest; run 'transcript_manifest.py write' first")
    listed = {}
    for line in MANIFEST.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            listed[e["path"]] = e

    missing = [p for p in sorted(listed)
               if not (REPO / p).exists()]
    modified = []
    for p in sorted(listed):
        fp = REPO / p
        if fp.exists() and sha256(fp) != listed[p]["sha256"]:
            modified.append(p)
    on_disk = {str(p.relative_to(REPO))
               for p in TRANSCRIPTS.rglob("*.jsonl")}
    unlisted = sorted(on_disk - set(listed))

    refs = referenced_transcripts()
    ref_missing = sorted(refs - on_disk)

    print(f"manifest entries : {len(listed)}")
    print(f"missing on disk  : {len(missing)}")
    print(f"hash mismatches  : {len(modified)}")
    print(f"on disk, unlisted: {len(unlisted)}")
    print(f"referenced by committed run records but absent: "
          f"{len(ref_missing)}")
    for label, items in (("MISSING", missing), ("MODIFIED", modified),
                         ("UNLISTED", unlisted), ("REF-MISSING", ref_missing)):
        for p in items[:20]:
            print(f"  {label}: {p}")
        if len(items) > 20:
            print(f"  {label}: ... and {len(items) - 20} more")
    sys.exit(1 if (missing or modified or unlisted or ref_missing) else 0)


if __name__ == "__main__":
    main()
