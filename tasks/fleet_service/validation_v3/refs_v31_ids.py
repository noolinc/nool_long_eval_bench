#!/usr/bin/env python3
"""Subset-parametrized ids-cluster reference (v3.1): t8 t33 t34 t35.

emit(ws, enabled) writes util/ids.go implementing exactly the tickets in
`enabled`. The empty set reproduces the starter file byte-for-byte; the
full set is byte-identical to refs.apply_ids output; every subset compiles
and is gofmt-clean.
"""
import os

TICKETS = ["t8", "t33", "t34", "t35"]

# ---------------- fixed fragments (must match refs.IDS bytes) ----------------

_NEWID_BASE = '''// NewID returns a fresh identifier of the form "<kind>-<n>".
func NewID(kind string) string {
\tcounter++
%s\treturn fmt.Sprintf("%%s-%%d", kind, counter)
}'''

_NEWID_NS = '''// NewID returns a fresh identifier of the form "<kind>-<n>", namespaced (t8).
func NewID(kind string) string {
\tcounter++
%s\tid := fmt.Sprintf("%%s-%%d", kind, counter)
\tif idNS != "" {
\t\treturn idNS + "/" + id
\t}
\treturn id
}'''

_PERKIND_LINE = "\tperKind[kind]++\n"

_SET_NS = '''// SetIDNamespace (t8).
func SetIDNamespace(ns string) { idNS = ns }'''

_RESET = '''// ResetIDs restores the counter; test helper.
func ResetIDs() { counter = 0 }'''

_VALID_ID = '''// ValidID (t33): id ends with kind + "-" + digits; any prefix permitted.
func ValidID(id, kind string) bool {
\ti := strings.LastIndex(id, "-")
\tif i < 0 || i+1 >= len(id) {
\t\treturn false
\t}
\tfor _, c := range id[i+1:] {
\t\tif c < '0' || c > '9' {
\t\t\treturn false
\t\t}
\t}
\treturn strings.HasSuffix(id[:i], kind)
}'''

_ID_COUNT = '''// IDCount (t34): identifiers issued for kind in this process.
func IDCount(kind string) int { return perKind[kind] }'''

_KIND_OF = '''// KindOf (t35): segment after the last '/' and before the final '-'.
func KindOf(id string) string {
\tif j := strings.LastIndex(id, "/"); j >= 0 {
\t\tid = id[j+1:]
\t}
\ti := strings.LastIndex(id, "-")
\tif i <= 0 || i+1 >= len(id) {
\t\treturn ""
\t}
\tfor _, c := range id[i+1:] {
\t\tif c < '0' || c > '9' {
\t\t\treturn ""
\t\t}
\t}
\treturn id[:i]
}'''

# ---------------- composition ----------------

def _imports(enabled):
    if "t33" in enabled or "t35" in enabled:
        return 'import (\n\t"fmt"\n\t"strings"\n)'
    return 'import "fmt"'

def _vars(enabled):
    specs = [("counter", "int")]  # (name, type) or (name, "= value")
    if "t8" in enabled:
        specs.append(("idNS", "string"))
    if "t34" in enabled:
        specs.append(("perKind", "= map[string]int{}"))
    if len(specs) == 1:
        return "var counter int"
    width = max(len(n) for n, _ in specs)
    lines = []
    for n, rhs in specs:
        lines.append("\t%s %s" % (n.ljust(width), rhs))
    return "var (\n%s\n)" % "\n".join(lines)

def _new_id(enabled):
    per_kind = _PERKIND_LINE if "t34" in enabled else ""
    tmpl = _NEWID_NS if "t8" in enabled else _NEWID_BASE
    return tmpl % per_kind

def render(enabled):
    """Return util/ids.go content implementing exactly `enabled`."""
    enabled = set(enabled)
    unknown = enabled - set(TICKETS)
    if unknown:
        raise ValueError("unknown ids tickets: %s" % sorted(unknown))
    parts = ["package util", _imports(enabled), _vars(enabled), _new_id(enabled)]
    if "t8" in enabled:
        parts.append(_SET_NS)
    parts.append(_RESET)
    if "t33" in enabled:
        parts.append(_VALID_ID)
    if "t34" in enabled:
        parts.append(_ID_COUNT)
    if "t35" in enabled:
        parts.append(_KIND_OF)
    return "\n\n".join(parts) + "\n"

def emit(ws, enabled):
    """Write ids-cluster files implementing exactly `enabled` into ws."""
    p = os.path.join(ws, "util", "ids.go")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(render(enabled))
