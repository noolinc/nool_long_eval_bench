"""Scripted no-LLM adapter: deterministic per-ticket edits for harness
validation at zero cost.

Carries real, minimal solutions for the 8 v1-corpus tickets (tickets.json;
same ids and hidden acceptance tests as corpus v3's t1-t8), applied as
targeted string edits against whatever tree the worktree currently holds.
Edits are deliberately conflict-prone in the same way real agent output is:
t3 and t7 both append a handler AND insert a route at the same anchor in
api/router.go, so from a shared base they produce a genuine textual merge
conflict — and regenerating either against a main that already contains the
other applies cleanly. That makes the git_retry arm's full recovery ladder
(conflict -> rebase fails -> re-run agent -> clean merge) reachable
deterministically, without an LLM or a network call.

Unknown ticket ids (anything outside t1-t8) get a marker-comment edit so
the harness plumbing still sees a change; their acceptance legitimately
fails. Do not pool scripted-adapter records with real-model results — the
harness records harness="scripted" in provenance for exactly that reason.
"""
import re
import time
from pathlib import Path

# ---------------------------------------------------------------- helpers


def _append(ws, rel, block):
    p = Path(ws) / rel
    p.write_text(p.read_text().rstrip() + "\n\n" + block.strip() + "\n")


def _replace(ws, rel, old, new, required=True):
    p = Path(ws) / rel
    s = p.read_text()
    if old not in s:
        if required:
            raise RuntimeError(f"scripted edit anchor missing in {rel}: {old!r}")
        return
    p.write_text(s.replace(old, new, 1))


def _write(ws, rel, content):
    p = Path(ws) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


# ------------------------------------------------------------- solutions


def _t1(ws):
    _append(ws, "service/users.go", '''
// Deactivate marks a user inactive; ErrNotFound for a missing id.
func (u *Users) Deactivate(id string) error {
	usr, err := u.Get(id)
	if err != nil {
		return err
	}
	usr.Active = false
	b, err := json.Marshal(usr)
	if err != nil {
		return err
	}
	u.S.Put("user/"+usr.ID, b)
	return nil
}''')


def _t2(ws):
    _append(ws, "service/billing.go", '''
// DiscountedInvoice applies a whole-percent discount, floors to cents,
// then invoices the discounted subtotal.
func DiscountedInvoice(subtotalCents, discountPct int) int {
	return Invoice(subtotalCents * (100 - discountPct) / 100)
}''')
    _append(ws, "service/orders.go", '''
// TotalWithDiscount invoices a user's order total under a discount.
func (o *Orders) TotalWithDiscount(userID string, discountPct int) int {
	return DiscountedInvoice(o.TotalFor(userID), discountPct)
}''')


def _t3(ws):
    _append(ws, "api/handlers.go", '''
func (a *App) handleUsersCount(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK,
		map[string]int{"count": len(a.Users.S.Keys("user/"))})
}''')
    _replace(ws, "api/router.go", "\treturn mux\n}",
             '\tmux.HandleFunc("/users/count", a.handleUsersCount)\n'
             "\treturn mux\n}")


def _t4(ws):
    _replace(ws, "store/memstore.go",
             "// Mem is an in-memory KV implementation safe for concurrent use.\n"
             "type Mem struct {\n\tmu   sync.RWMutex\n\tdata map[string][]byte\n}\n",
             "// Mem is an in-memory KV implementation safe for concurrent use.\n"
             "type Mem struct {\n\tmu   sync.RWMutex\n\tdata map[string][]byte\n"
             "\texp  map[string]int64\n}\n")
    _replace(ws, "store/memstore.go",
             "func NewMem() *Mem { return &Mem{data: map[string][]byte{}} }",
             "func NewMem() *Mem {\n"
             "\treturn &Mem{data: map[string][]byte{}, exp: map[string]int64{}}\n"
             "}\n\n"
             "// PutTTL stores a value visible until the logical clock\n"
             "// reaches expireAtMs (util.Now()-based).\n"
             "func (m *Mem) PutTTL(key string, value []byte, expireAtMs int64) {\n"
             "\tm.mu.Lock()\n\tdefer m.mu.Unlock()\n"
             "\tm.data[key] = value\n"
             "\tm.exp[key] = expireAtMs\n"
             "}\n\n"
             "func (m *Mem) expired(key string) bool {\n"
             "\te, ok := m.exp[key]\n"
             "\treturn ok && util.Now() >= e\n"
             "}")
    _replace(ws, "store/memstore.go",
             "\tv, ok := m.data[key]\n\treturn v, ok",
             "\tif m.expired(key) {\n\t\treturn nil, false\n\t}\n"
             "\tv, ok := m.data[key]\n\treturn v, ok")
    _replace(ws, "store/memstore.go",
             "\tfor k := range m.data {\n\t\tif strings.HasPrefix(k, prefix) {",
             "\tfor k := range m.data {\n"
             "\t\tif m.expired(k) {\n\t\t\tcontinue\n\t\t}\n"
             "\t\tif strings.HasPrefix(k, prefix) {")
    _replace(ws, "store/memstore.go",
             'import (\n\t"sort"\n\t"strings"\n\t"sync"\n)',
             'import (\n\t"sort"\n\t"strings"\n\t"sync"\n\n'
             '\t"bench/fleetsvc/util"\n)')


def _t5(ws):
    _write(ws, "util/audit.go", '''package util

import "sync"

var (
	auditMu  sync.Mutex
	auditLog []string
)

// Audit appends one entry to the process-wide audit log.
func Audit(entry string) {
	auditMu.Lock()
	defer auditMu.Unlock()
	auditLog = append(auditLog, entry)
}

// AuditLog returns a copy of all audit entries so far.
func AuditLog() []string {
	auditMu.Lock()
	defer auditMu.Unlock()
	out := make([]string, len(auditLog))
	copy(out, auditLog)
	return out
}
''')
    _replace(ws, "service/orders.go",
             '\to.S.Put("order/"+ord.ID, b)\n\treturn ord, nil',
             '\to.S.Put("order/"+ord.ID, b)\n'
             '\tutil.Audit("order.created " + ord.ID)\n'
             "\treturn ord, nil")


def _t6(ws):
    _append(ws, "model/user.go", '''
// ValidEmail reports whether e looks like a plausible email address.
func ValidEmail(e string) bool {
	at := -1
	for i, c := range e {
		switch c {
		case '@':
			if at >= 0 {
				return false
			}
			at = i
		case ' ':
			return false
		}
	}
	if at <= 0 || at == len(e)-1 {
		return false
	}
	dot := false
	for i := at + 2; i < len(e)-1; i++ {
		if e[i] == '.' {
			dot = true
		}
	}
	return dot
}''')
    _replace(ws, "service/users.go",
             "func (u *Users) Create(email string) (*model.User, error) {\n",
             "func (u *Users) Create(email string) (*model.User, error) {\n"
             "\tif !model.ValidEmail(email) {\n"
             '\t\treturn nil, errors.New("invalid email")\n'
             "\t}\n")


def _t7(ws):
    _append(ws, "api/handlers.go", '''
func (a *App) handleOrdersCount(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK,
		map[string]int{"count": len(a.Orders.S.Keys("order/"))})
}''')
    _replace(ws, "api/router.go", "\treturn mux\n}",
             '\tmux.HandleFunc("/orders/count", a.handleOrdersCount)\n'
             "\treturn mux\n}")


def _t8(ws):
    _write(ws, "util/ids.go", '''package util

import "fmt"

var (
	counter     int
	idNamespace string
)

// SetIDNamespace prefixes subsequently minted IDs with "<ns>/"; the empty
// namespace restores the default "<kind>-<n>" form.
func SetIDNamespace(ns string) { idNamespace = ns }

// NewID returns a fresh identifier of the form "[<ns>/]<kind>-<n>".
func NewID(kind string) string {
	counter++
	if idNamespace != "" {
		return fmt.Sprintf("%s/%s-%d", idNamespace, kind, counter)
	}
	return fmt.Sprintf("%s-%d", kind, counter)
}

// ResetIDs restores the counter; test helper.
func ResetIDs() { counter = 0 }
''')


SOLUTIONS = {"t1": _t1, "t2": _t2, "t3": _t3, "t4": _t4,
             "t5": _t5, "t6": _t6, "t7": _t7, "t8": _t8}

_TICKET_RE = re.compile(r"Ticket\s+([a-z]?t?\d+)\s", re.IGNORECASE)


# ------------------------------------------------------- adapter surface


def preflight():
    return {"adapter": "scripted", "note": "deterministic, no LLM, $0"}


def run(cwd, prompt, model, max_turns=30, timeout_s=600,
        transcript_path=None, env=None):
    t0 = time.monotonic()
    m = _TICKET_RE.search(prompt)
    tid = m.group(1) if m else "unknown"
    err = None
    try:
        if tid in SOLUTIONS:
            SOLUTIONS[tid](cwd)
        else:
            # marker edit: plumbing still sees a change; acceptance fails
            _append(Path(cwd), "smoke_test.go",
                    f"// scripted-adapter marker for {tid}")
    except Exception as e:  # surfaced in the record, not swallowed
        err = f"{type(e).__name__}: {e}"
    if transcript_path:
        import json as _json
        Path(transcript_path).write_text(
            _json.dumps({"adapter": "scripted", "ticket": tid,
                         "error": err}) + "\n")
    return {"adapter": "scripted", "exit_code": 1 if err else 0,
            "timed_out": False,
            "wall_ms": round((time.monotonic() - t0) * 1000.0, 1),
            "stderr_tail": err or "", "model_reported": "scripted",
            "num_turns": 1, "tool_calls": 1, "tokens_in": 0, "tokens_out": 0,
            "cache_read_tokens": 0, "cache_creation_tokens": 0,
            "cost_usd": 0.0, "is_error": bool(err)}
