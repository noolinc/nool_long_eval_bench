"""Frozen-protocol and language-neutral fleet-corpus validation helpers."""

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PROTOCOL = REPO / "protocols" / "fleet_v4.json"


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_protocol(path=DEFAULT_PROTOCOL):
    path = Path(path).resolve()
    data = json.loads(path.read_text())
    digest = file_sha256(path)
    pin = path.with_suffix(".sha256")
    if not pin.exists():
        raise ValueError(f"frozen protocol pin missing: {pin}")
    expected = pin.read_text().split()[0]
    if digest != expected:
        raise ValueError(f"frozen protocol hash {digest} != pin {expected}")
    required = {
        "protocol_id", "status", "primary_unit",
        "minimum_repetitions_per_arm_cell", "primary_comparisons",
        "required_corpus_fields", "required_commands", "required_metrics",
        "analysis_rules",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"protocol missing fields: {missing}")
    if data["status"] != "frozen":
        raise ValueError("evidence runs require a frozen protocol")
    if data["primary_unit"] != "run":
        raise ValueError("fleet protocol primary unit must be 'run'")
    return data, digest, path


def validate_corpus(corpus, protocol):
    missing = sorted(set(protocol["required_corpus_fields"]) - set(corpus))
    if missing:
        raise ValueError(f"corpus missing protocol fields: {missing}")
    commands = corpus.get("commands") or {}
    missing_commands = sorted(set(protocol["required_commands"]) - set(commands))
    if missing_commands:
        raise ValueError(f"corpus missing commands: {missing_commands}")
    for name, command in commands.items():
        if not isinstance(command, list) or not command or not all(
                isinstance(part, str) and part for part in command):
            raise ValueError(f"commands.{name} must be a non-empty string array")
    if "{ticket}" not in " ".join(commands["accept"]):
        raise ValueError("commands.accept must contain a {ticket} placeholder")
    ids = [ticket.get("id") for ticket in corpus.get("tickets", [])]
    if not ids or any(not tid for tid in ids) or len(ids) != len(set(ids)):
        raise ValueError("ticket ids must be present and unique")
    for ticket in corpus["tickets"]:
        for key in ("id", "title", "spec", "footprint"):
            if key not in ticket:
                raise ValueError(f"ticket {ticket.get('id')} missing {key}")
        if not isinstance(ticket["footprint"], list):
            raise ValueError(f"ticket {ticket['id']} footprint must be a list")
    return True


def protocol_provenance(path=DEFAULT_PROTOCOL):
    protocol, digest, resolved = load_protocol(path)
    try:
        display_path = str(resolved.relative_to(REPO))
    except ValueError:
        display_path = str(resolved)
    return {
        "id": protocol["protocol_id"],
        "sha256": digest,
        "path": display_path,
        "status": protocol["status"],
        "primary_unit": protocol["primary_unit"],
    }, protocol
