#!/usr/bin/env python3
"""Subset-parametrized reference generator for the api cluster (corpus v3).

emit(ws, enabled) writes api/handlers.go and api/router.go implementing
exactly the tickets in `enabled`; disabled tickets keep starter semantics
(endpoint absent from Router, starter handleUserGet error shape, no wrap
behavior). emit(ws, set(TICKETS)) is byte-identical to refs.apply_api(ws)
output. Drop-in replacement for refs.apply_api in the canonical apply order
(billing, users, orders, store, api, ids, clock, fillers); handlers assume
the earlier clusters' service-layer symbols (Users.Create/Get,
Orders.Create/TotalFor) are present.

Layering: the wrap() middleware exists iff any of t12/t23/t13/t24 is
enabled, and then carries only the enabled behaviors; every registered
route — base or ticket-added — goes through it, since each of those
tickets specifies "every request served through Router()".
"""
import os

TICKETS = ["t3", "t7", "t12", "t13", "t14", "t23", "t24", "t38", "t39", "t40"]

# Router-wide middleware tickets, in the reference wrap-body (and comment)
# order: request-id, server identity, request log, blocklist.
_WRAP_TICKETS = ("t12", "t23", "t13", "t24")


def _w(ws, rel, content):
    p = os.path.join(ws, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)


# ---------------- api/handlers.go ----------------

_H_T40_CONST = '''
// Version (t40).
const Version = "1"
'''

_H_T13_LOG = '''
var (
	reqMu  sync.Mutex
	reqLog []string
)

// RequestLog (t13): URL paths of every request served through Router, in order.
func RequestLog() []string {
	reqMu.Lock()
	defer reqMu.Unlock()
	out := make([]string, len(reqLog))
	copy(out, reqLog)
	return out
}

func recordRequest(path string) {
	reqMu.Lock()
	defer reqMu.Unlock()
	reqLog = append(reqLog, path)
}
'''

_H_WRITE_JSON = '''
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
'''

_H_USER_CREATE = '''
func (a *App) handleUserCreate(w http.ResponseWriter, r *http.Request) {
	email := r.URL.Query().Get("email")
	u, err := a.Users.Create(email)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, u)
}
'''

_H_USER_GET_T14 = '''
// handleUserGet errors use the t14 envelope: {"error": msg, "code": status}.
func (a *App) handleUserGet(w http.ResponseWriter, r *http.Request) {
	u, err := a.Users.Get(r.URL.Query().Get("id"))
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]any{"error": err.Error(), "code": http.StatusNotFound})
		return
	}
	writeJSON(w, http.StatusOK, u)
}
'''

_H_USER_GET_STARTER = '''
func (a *App) handleUserGet(w http.ResponseWriter, r *http.Request) {
	u, err := a.Users.Get(r.URL.Query().Get("id"))
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, u)
}
'''

_H_ORDER_CREATE = '''
func (a *App) handleOrderCreate(w http.ResponseWriter, r *http.Request) {
	ord, err := a.Orders.Create(r.URL.Query().Get("user_id"), atoi(r.URL.Query().Get("cents")))
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, ord)
}
'''

_H_T3 = '''
// handleUsersCount (t3).
func (a *App) handleUsersCount(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]int{"count": len(a.Users.S.Keys("user/"))})
}
'''

_H_T7 = '''
// handleOrdersCount (t7).
func (a *App) handleOrdersCount(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]int{"count": len(a.Orders.S.Keys("order/"))})
}
'''

_H_T39 = '''
// handleOrdersTotal (t39).
func (a *App) handleOrdersTotal(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]int{"total": a.Orders.TotalFor(r.URL.Query().Get("user_id"))})
}
'''

_H_T38 = '''
// handleHealth (t38).
func (a *App) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}
'''

_H_T40_HANDLER = '''
// handleVersion (t40).
func (a *App) handleVersion(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"version": Version})
}
'''

_H_ATOI = '''
func atoi(s string) int {
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return n
		}
		n = n*1
		n = n*10 + int(c-'0')
	}
	return n
}
'''


def _handlers_go(on):
    parts = ['package api\n\nimport (\n\t"encoding/json"\n\t"net/http"\n']
    if "t13" in on:
        parts.append('\t"sync"\n')
    parts.append(')\n')
    if "t40" in on:
        parts.append(_H_T40_CONST)
    if "t13" in on:
        parts.append(_H_T13_LOG)
    parts.append(_H_WRITE_JSON)
    parts.append(_H_USER_CREATE)
    parts.append(_H_USER_GET_T14 if "t14" in on else _H_USER_GET_STARTER)
    parts.append(_H_ORDER_CREATE)
    if "t3" in on:
        parts.append(_H_T3)
    if "t7" in on:
        parts.append(_H_T7)
    if "t39" in on:
        parts.append(_H_T39)
    if "t38" in on:
        parts.append(_H_T38)
    if "t40" in on:
        parts.append(_H_T40_HANDLER)
    parts.append(_H_ATOI)
    return "".join(parts)


# ---------------- api/router.go ----------------

_R_APP = '''
type App struct {
	Users  *service.Users
	Orders *service.Orders
}
'''

_WRAP_LABELS = {
    "t12": "request-id header (t12)",
    "t23": "server identity header (t23)",
    "t13": "request log (t13)",
    "t24": "blocklist (t24)",
}

_WRAP_BODY = {
    "t12": '\t\tw.Header().Set("X-Request-Id", util.NewID("req"))\n',
    "t23": '\t\tw.Header().Set("X-Served-By", "fleetsvc")\n',
    "t13": '\t\trecordRequest(r.URL.Path)\n',
    "t24": '''\t\tif r.Header.Get("X-Blocked") == "true" {
			w.WriteHeader(http.StatusForbidden)
			return
		}
''',
}

# (path, handler, gating ticket or None) in reference registration order.
_ROUTES = [
    ("/users/create", "a.handleUserCreate", None),
    ("/users/get", "a.handleUserGet", None),
    ("/users/count", "a.handleUsersCount", "t3"),
    ("/orders/create", "a.handleOrderCreate", None),
    ("/orders/count", "a.handleOrdersCount", "t7"),
    ("/orders/total", "a.handleOrdersTotal", "t39"),
    ("/health", "a.handleHealth", "t38"),
    ("/version", "a.handleVersion", "t40"),
]


def _wrap_comment(wrap_on):
    items = [_WRAP_LABELS[t] for t in _WRAP_TICKETS if t in wrap_on]
    text = "wrap applies the Router-wide behaviors: " + ", ".join(items) + "."
    lines, cur = [], "//"
    for word in text.split(" "):
        cand = cur + " " + word
        if len(cand) > 68 and cur != "//":
            lines.append(cur)
            cur = "// " + word
        else:
            cur = cand
    lines.append(cur)
    return "".join(l + "\n" for l in lines)


def _router_go(on):
    wrap_on = [t for t in _WRAP_TICKETS if t in on]
    parts = ['package api\n\nimport (\n\t"net/http"\n\n\t"bench/fleetsvc/service"\n']
    if "t12" in on:
        parts.append('\t"bench/fleetsvc/util"\n')
    parts.append(')\n')
    parts.append(_R_APP)
    if wrap_on:
        parts.append('\n')
        parts.append(_wrap_comment(wrap_on))
        parts.append('func wrap(h http.HandlerFunc) http.HandlerFunc {\n')
        parts.append('\treturn func(w http.ResponseWriter, r *http.Request) {\n')
        for t in wrap_on:
            parts.append(_WRAP_BODY[t])
        parts.append('\t\th(w, r)\n\t}\n}\n')
    parts.append('\n// Router wires all HTTP endpoints.\n')
    parts.append('func (a *App) Router() *http.ServeMux {\n')
    parts.append('\tmux := http.NewServeMux()\n')
    for path, handler, gate in _ROUTES:
        if gate is not None and gate not in on:
            continue
        h = 'wrap(%s)' % handler if wrap_on else handler
        parts.append('\tmux.HandleFunc("%s", %s)\n' % (path, h))
    parts.append('\treturn mux\n}\n')
    return "".join(parts)


def emit(ws, enabled):
    on = set(enabled)
    unknown = on - set(TICKETS)
    if unknown:
        raise ValueError("unknown api tickets: %s" % sorted(unknown))
    _w(ws, "api/handlers.go", _handlers_go(on))
    _w(ws, "api/router.go", _router_go(on))
