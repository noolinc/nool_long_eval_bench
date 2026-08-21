#!/usr/bin/env python3
"""Combined reference implementations for corpus v3 validation.

Each apply_* writes full replacement files implementing that cluster's
tickets correctly and simultaneously. apply_all() = grand workspace.
"""
import os, shutil

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
STARTER = os.path.join(REPO, "tasks/fleet_service/starter")

def W(ws, rel, content):
    p = os.path.join(ws, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)

def new_ws(root, name):
    ws = os.path.join(root, name)
    if os.path.exists(ws):
        shutil.rmtree(ws)
    shutil.copytree(STARTER, ws)
    return ws

# ---------------- billing: t9 t10 t11 t21 t22 + t2 helper ----------------
BILLING = '''package service

// TaxBasisPoints is applied by Invoice on top of the order subtotal.
const TaxBasisPoints = 1000 // 10.00%

// Invoice: negative subtotals count as zero (t21); a 25c processing fee is
// added before tax (t10); subtotals >= 100000 pay no tax (t11); the result
// is at least 50 (t9) and at most 5000000, cap applied last (t22).
func Invoice(subtotalCents int) int {
	if subtotalCents < 0 {
		subtotalCents = 0
	}
	withFee := subtotalCents + 25
	var amt int
	if subtotalCents >= 100000 {
		amt = withFee
	} else {
		amt = withFee + withFee*TaxBasisPoints/10000
	}
	if amt < 50 {
		amt = 50
	}
	if amt > 5000000 {
		amt = 5000000
	}
	return amt
}

// DiscountedInvoice (t2): discount, floor, then invoice like Invoice does.
func DiscountedInvoice(subtotalCents, discountPct int) int {
	return Invoice(subtotalCents * (100 - discountPct) / 100)
}
'''

def apply_billing(ws):
    W(ws, "service/billing.go", BILLING)
    # t2's TotalWithDiscount without other orders-cluster changes
    with open(os.path.join(ws, "service/orders.go")) as f:
        src = f.read()
    if "TotalWithDiscount" not in src:
        src += '''
func (o *Orders) TotalWithDiscount(userID string, discountPct int) int {
	return DiscountedInvoice(o.TotalFor(userID), discountPct)
}
'''
        W(ws, "service/orders.go", src)

# ---------------- model/user: struct + t6 t36 t37 ----------------
MODEL_USER = '''package model

import "strings"

type User struct {
	ID     string
	Email  string
	Active bool
}

// ValidEmail (t6): exactly one '@', at least one '.' after it, no spaces.
func ValidEmail(e string) bool {
	if strings.Count(e, "@") != 1 || strings.ContainsAny(e, " \\t") {
		return false
	}
	at := strings.Index(e, "@")
	return strings.Contains(e[at+1:], ".")
}

// DisplayName (t36): part of Email before the first '@'.
func (u *User) DisplayName() string {
	if i := strings.Index(u.Email, "@"); i >= 0 {
		return u.Email[:i]
	}
	return u.Email
}

// Clone (t37): field-complete copy.
func (u *User) Clone() *User {
	c := *u
	return &c
}
'''

# ---------------- users: t1 t6 t20 t27 t28 t29 ----------------
USERS = '''package service

import (
	"encoding/json"
	"errors"
	"sort"
	"strings"

	"bench/fleetsvc/model"
	"bench/fleetsvc/store"
	"bench/fleetsvc/util"
)

var ErrNotFound = errors.New("not found")

type Users struct {
	S store.KV
}

func (u *Users) Create(email string) (*model.User, error) {
	email = strings.TrimSpace(email)  // t29: trim first
	email = strings.ToLower(email)    // t27: then lowercase
	if !model.ValidEmail(email) {     // t6
		return nil, errors.New("invalid email")
	}
	for _, k := range u.S.Keys("user/") { // t28: duplicate check on stored form
		b, ok := u.S.Get(k)
		if !ok {
			continue
		}
		var ex model.User
		if json.Unmarshal(b, &ex) == nil && ex.Email == email {
			return nil, errors.New("duplicate email")
		}
	}
	usr := &model.User{ID: util.NewID("user"), Email: email, Active: true}
	b, err := json.Marshal(usr)
	if err != nil {
		return nil, err
	}
	u.S.Put("user/"+usr.ID, b)
	return usr, nil
}

func (u *Users) Get(id string) (*model.User, error) {
	b, ok := u.S.Get("user/" + id)
	if !ok {
		return nil, ErrNotFound
	}
	var usr model.User
	if err := json.Unmarshal(b, &usr); err != nil {
		return nil, err
	}
	return &usr, nil
}

// Deactivate (t1).
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
}

// List (t20): all users sorted by ID ascending.
func (u *Users) List() ([]*model.User, error) {
	var out []*model.User
	for _, k := range u.S.Keys("user/") {
		b, ok := u.S.Get(k)
		if !ok {
			continue
		}
		var usr model.User
		if err := json.Unmarshal(b, &usr); err != nil {
			return nil, err
		}
		out = append(out, &usr)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out, nil
}
'''

def apply_users(ws):
    W(ws, "service/users.go", USERS)
    W(ws, "model/user.go", MODEL_USER)

# ---------------- orders: t2 t5 t18 t30 t31 t32 + model/order ----------------
MODEL_ORDER = '''package model

type Order struct {
	ID        string
	UserID    string
	Cents     int
	Status    string // t18
	CreatedAt int64  // t31
}
'''

ORDERS = '''package service

import (
	"encoding/json"
	"errors"

	"bench/fleetsvc/model"
	"bench/fleetsvc/store"
	"bench/fleetsvc/util"
)

type Orders struct {
	S store.KV
}

func (o *Orders) Create(userID string, cents int) (*model.Order, error) {
	if cents <= 0 { // t30
		return nil, errors.New("non-positive amount")
	}
	ord := &model.Order{ID: util.NewID("order"), UserID: userID, Cents: cents, CreatedAt: util.Now()} // t31
	b, err := json.Marshal(ord)
	if err != nil {
		return nil, err
	}
	o.S.Put("order/"+ord.ID, b)
	util.Audit("order.created " + ord.ID) // t5
	return ord, nil
}

func (o *Orders) Get(id string) (*model.Order, error) {
	b, ok := o.S.Get("order/" + id)
	if !ok {
		return nil, ErrNotFound
	}
	var ord model.Order
	if err := json.Unmarshal(b, &ord); err != nil {
		return nil, err
	}
	return &ord, nil
}

// SetStatus (t18).
func (o *Orders) SetStatus(id, status string) error {
	ord, err := o.Get(id)
	if err != nil {
		return err
	}
	ord.Status = status
	b, err := json.Marshal(ord)
	if err != nil {
		return err
	}
	o.S.Put("order/"+ord.ID, b)
	return nil
}

// TotalFor sums positive-cents orders for a user (t32 ignores the rest).
func (o *Orders) TotalFor(userID string) int {
	total := 0
	for _, k := range o.S.Keys("order/") {
		b, ok := o.S.Get(k)
		if !ok {
			continue
		}
		var ord model.Order
		if json.Unmarshal(b, &ord) == nil && ord.UserID == userID && ord.Cents > 0 {
			total += ord.Cents
		}
	}
	return total
}

// TotalWithDiscount (t2).
func (o *Orders) TotalWithDiscount(userID string, discountPct int) int {
	return DiscountedInvoice(o.TotalFor(userID), discountPct)
}
'''

AUDIT = '''package util

import "sync"

var (
	auditMu  sync.Mutex
	auditLog []string
)

// Audit (t5): append-only event record.
func Audit(event string) {
	auditMu.Lock()
	defer auditMu.Unlock()
	auditLog = append(auditLog, event)
}

func AuditLog() []string {
	auditMu.Lock()
	defer auditMu.Unlock()
	out := make([]string, len(auditLog))
	copy(out, auditLog)
	return out
}
'''

def apply_orders(ws):
    W(ws, "service/orders.go", ORDERS)
    W(ws, "model/order.go", MODEL_ORDER)
    W(ws, "util/audit.go", AUDIT)
    W(ws, "service/billing.go", BILLING)  # DiscountedInvoice dependency (t2 spans both)

# ---------------- store: t4 t15 t16 t17 t25 t26 ----------------
KV = '''package store

// KV is the storage contract used by all services.
type KV interface {
	Get(key string) ([]byte, bool)
	Put(key string, value []byte)
	PutTTL(key string, value []byte, expiresAt int64) // t4
	Delete(key string)
	Keys(prefix string) []string
}
'''

MEMSTORE = '''package store

import (
	"sort"
	"strings"
	"sync"

	"bench/fleetsvc/util"
)

type entry struct {
	val []byte
	exp int64 // 0 = never expires
}

// Mem is an in-memory KV implementation safe for concurrent use.
type Mem struct {
	mu   sync.RWMutex
	data map[string]entry
}

func NewMem() *Mem { return &Mem{data: map[string]entry{}} }

func cp(b []byte) []byte {
	out := make([]byte, len(b))
	copy(out, b)
	return out
}

func (e entry) visible() bool { return e.exp == 0 || util.Now() < e.exp }

func (m *Mem) Get(key string) ([]byte, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	e, ok := m.data[key]
	if !ok || !e.visible() {
		return nil, false
	}
	return cp(e.val), true // t26: copy out
}

func (m *Mem) Put(key string, value []byte) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data[key] = entry{val: cp(value)} // t26: copy in
}

// PutTTL (t4): entry invisible once util.Now() >= expiresAt.
func (m *Mem) PutTTL(key string, value []byte, expiresAt int64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data[key] = entry{val: cp(value), exp: expiresAt}
}

func (m *Mem) Delete(key string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.data, key)
}

func (m *Mem) Keys(prefix string) []string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	var out []string
	for k, e := range m.data {
		if strings.HasPrefix(k, prefix) && e.visible() {
			out = append(out, k)
		}
	}
	sort.Strings(out)
	return out
}

// Len (t15): number of visible entries.
func (m *Mem) Len() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	n := 0
	for _, e := range m.data {
		if e.visible() {
			n++
		}
	}
	return n
}

// Clear (t16).
func (m *Mem) Clear() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data = map[string]entry{}
}

// Snapshot (t17): deep copy of current visible entries.
func (m *Mem) Snapshot() map[string][]byte {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := map[string][]byte{}
	for k, e := range m.data {
		if e.visible() {
			out[k] = cp(e.val)
		}
	}
	return out
}

// Restore (t17): replace all entries with a deep copy of s.
func (m *Mem) Restore(s map[string][]byte) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data = map[string]entry{}
	for k, v := range s {
		m.data[k] = entry{val: cp(v)}
	}
}

// Range (t25): visible entries with prefix, ascending, early stop on false.
func (m *Mem) Range(prefix string, fn func(key string, value []byte) bool) {
	m.mu.RLock()
	keys := []string{}
	for k, e := range m.data {
		if strings.HasPrefix(k, prefix) && e.visible() {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)
	vals := map[string][]byte{}
	for _, k := range keys {
		vals[k] = cp(m.data[k].val)
	}
	m.mu.RUnlock()
	for _, k := range keys {
		if !fn(k, vals[k]) {
			return
		}
	}
}
'''

def apply_store(ws):
    W(ws, "store/kv.go", KV)
    W(ws, "store/memstore.go", MEMSTORE)

# ---------------- api: t3 t7 t12 t13 t14 t23 t24 t38 t39 t40 ----------------
HANDLERS = '''package api

import (
	"encoding/json"
	"net/http"
	"sync"
)

// Version (t40).
const Version = "1"

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

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func (a *App) handleUserCreate(w http.ResponseWriter, r *http.Request) {
	email := r.URL.Query().Get("email")
	u, err := a.Users.Create(email)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, u)
}

// handleUserGet errors use the t14 envelope: {"error": msg, "code": status}.
func (a *App) handleUserGet(w http.ResponseWriter, r *http.Request) {
	u, err := a.Users.Get(r.URL.Query().Get("id"))
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]any{"error": err.Error(), "code": http.StatusNotFound})
		return
	}
	writeJSON(w, http.StatusOK, u)
}

func (a *App) handleOrderCreate(w http.ResponseWriter, r *http.Request) {
	ord, err := a.Orders.Create(r.URL.Query().Get("user_id"), atoi(r.URL.Query().Get("cents")))
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, ord)
}

// handleUsersCount (t3).
func (a *App) handleUsersCount(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]int{"count": len(a.Users.S.Keys("user/"))})
}

// handleOrdersCount (t7).
func (a *App) handleOrdersCount(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]int{"count": len(a.Orders.S.Keys("order/"))})
}

// handleOrdersTotal (t39).
func (a *App) handleOrdersTotal(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]int{"total": a.Orders.TotalFor(r.URL.Query().Get("user_id"))})
}

// handleHealth (t38).
func (a *App) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// handleVersion (t40).
func (a *App) handleVersion(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"version": Version})
}

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

ROUTER = '''package api

import (
	"net/http"

	"bench/fleetsvc/service"
	"bench/fleetsvc/util"
)

type App struct {
	Users  *service.Users
	Orders *service.Orders
}

// wrap applies the Router-wide behaviors: request-id header (t12),
// server identity header (t23), request log (t13), blocklist (t24).
func wrap(h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Request-Id", util.NewID("req"))
		w.Header().Set("X-Served-By", "fleetsvc")
		recordRequest(r.URL.Path)
		if r.Header.Get("X-Blocked") == "true" {
			w.WriteHeader(http.StatusForbidden)
			return
		}
		h(w, r)
	}
}

// Router wires all HTTP endpoints.
func (a *App) Router() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/users/create", wrap(a.handleUserCreate))
	mux.HandleFunc("/users/get", wrap(a.handleUserGet))
	mux.HandleFunc("/users/count", wrap(a.handleUsersCount))
	mux.HandleFunc("/orders/create", wrap(a.handleOrderCreate))
	mux.HandleFunc("/orders/count", wrap(a.handleOrdersCount))
	mux.HandleFunc("/orders/total", wrap(a.handleOrdersTotal))
	mux.HandleFunc("/health", wrap(a.handleHealth))
	mux.HandleFunc("/version", wrap(a.handleVersion))
	return mux
}
'''

def apply_api(ws):
    W(ws, "api/handlers.go", HANDLERS)
    W(ws, "api/router.go", ROUTER)

# ---------------- ids: t8 t33 t34 t35 ----------------
IDS = '''package util

import (
	"fmt"
	"strings"
)

var (
	counter int
	idNS    string
	perKind = map[string]int{}
)

// NewID returns a fresh identifier of the form "<kind>-<n>", namespaced (t8).
func NewID(kind string) string {
	counter++
	perKind[kind]++
	id := fmt.Sprintf("%s-%d", kind, counter)
	if idNS != "" {
		return idNS + "/" + id
	}
	return id
}

// SetIDNamespace (t8).
func SetIDNamespace(ns string) { idNS = ns }

// ResetIDs restores the counter; test helper.
func ResetIDs() { counter = 0 }

// ValidID (t33): id ends with kind + "-" + digits; any prefix permitted.
func ValidID(id, kind string) bool {
	i := strings.LastIndex(id, "-")
	if i < 0 || i+1 >= len(id) {
		return false
	}
	for _, c := range id[i+1:] {
		if c < '0' || c > '9' {
			return false
		}
	}
	return strings.HasSuffix(id[:i], kind)
}

// IDCount (t34): identifiers issued for kind in this process.
func IDCount(kind string) int { return perKind[kind] }

// KindOf (t35): segment after the last '/' and before the final '-'.
func KindOf(id string) string {
	if j := strings.LastIndex(id, "/"); j >= 0 {
		id = id[j+1:]
	}
	i := strings.LastIndex(id, "-")
	if i <= 0 || i+1 >= len(id) {
		return ""
	}
	for _, c := range id[i+1:] {
		if c < '0' || c > '9' {
			return ""
		}
	}
	return id[:i]
}
'''

def apply_ids(ws):
    W(ws, "util/ids.go", IDS)

# ---------------- clock (t19) ----------------
CLOCK = '''package util

// Now returns the current logical time. Tests may override via SetNow.
var nowFn = func() int64 { return 1000 }

func Now() int64 { return nowFn() }

func SetNow(f func() int64) { nowFn = f }

// Since and Deadline (t19).
func Since(t int64) int64    { return Now() - t }
func Deadline(d int64) int64 { return Now() + d }
'''

def apply_clock(ws):
    W(ws, "util/clock.go", CLOCK)

# ---------------- fillers t41-t60 ----------------
FILLER_FILES = {
"util/truncate.go": '''package util

// Truncate (t41): first n runes.
func Truncate(s string, n int) string {
	if n <= 0 {
		return ""
	}
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n])
}
''',
"util/reverse.go": '''package util

// ReverseString (t42).
func ReverseString(s string) string {
	r := []rune(s)
	for i, j := 0, len(r)-1; i < j; i, j = i+1, j-1 {
		r[i], r[j] = r[j], r[i]
	}
	return string(r)
}
''',
"util/clamp.go": '''package util

// ClampInt (t43); lo wins when lo > hi.
func ClampInt(v, lo, hi int) int {
	if lo > hi {
		return lo
	}
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}
''',
"util/abs.go": '''package util

// AbsInt (t44).
func AbsInt(v int) int {
	if v < 0 {
		return -v
	}
	return v
}
''',
"util/backoff.go": '''package util

// Backoff (t45): 100 * 2^attempt ms capped at 10000; attempt <= 0 -> 100.
func Backoff(attempt int) int64 {
	if attempt <= 0 {
		return 100
	}
	v := int64(100)
	for i := 0; i < attempt; i++ {
		v *= 2
		if v >= 10000 {
			return 10000
		}
	}
	return v
}
''',
"util/slug.go": '''package util

import "strings"

// Slug (t46).
func Slug(s string) string {
	s = strings.ToLower(s)
	var b strings.Builder
	pendingDash := false
	for _, c := range s {
		alnum := (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
		if alnum {
			if pendingDash && b.Len() > 0 {
				b.WriteByte('-')
			}
			pendingDash = false
			b.WriteRune(c)
		} else {
			pendingDash = true
		}
	}
	return b.String()
}
''',
"model/money.go": '''package model

import "fmt"

// FormatCents (t47).
func FormatCents(c int) string {
	sign := ""
	if c < 0 {
		sign = "-"
		c = -c
	}
	return fmt.Sprintf("%s%d.%02d", sign, c/100, c%100)
}
''',
"model/zip.go": '''package model

// ValidZip (t48): exactly five ASCII digits.
func ValidZip(s string) bool {
	if len(s) != 5 {
		return false
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}
''',
"store/counter.go": '''package store

import "sync"

// Counter (t49).
type Counter struct {
	mu sync.Mutex
	n  int
}

func NewCounter() *Counter { return &Counter{} }

func (c *Counter) Inc() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.n++
	return c.n
}

func (c *Counter) Value() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.n
}
''',
"store/prefixcount.go": '''package store

// CountPrefix (t50).
func CountPrefix(kv KV, prefix string) int {
	return len(kv.Keys(prefix))
}
''',
"util/set.go": '''package util

// StringSet (t51).
type StringSet struct {
	m map[string]struct{}
}

func NewStringSet() *StringSet { return &StringSet{m: map[string]struct{}{}} }

func (s *StringSet) Add(v string)      { s.m[v] = struct{}{} }
func (s *StringSet) Has(v string) bool { _, ok := s.m[v]; return ok }
func (s *StringSet) Len() int          { return len(s.m) }
''',
"util/queue.go": '''package util

// Queue (t52): FIFO for strings.
type Queue struct {
	xs []string
}

func NewQueue() *Queue { return &Queue{} }

func (q *Queue) Push(s string) { q.xs = append(q.xs, s) }

func (q *Queue) Pop() (string, bool) {
	if len(q.xs) == 0 {
		return "", false
	}
	v := q.xs[0]
	q.xs = q.xs[1:]
	return v, true
}
''',
"util/stack.go": '''package util

// Stack (t53): LIFO for strings.
type Stack struct {
	xs []string
}

func NewStack() *Stack { return &Stack{} }

func (s *Stack) Push(v string) { s.xs = append(s.xs, v) }

func (s *Stack) Pop() (string, bool) {
	if len(s.xs) == 0 {
		return "", false
	}
	v := s.xs[len(s.xs)-1]
	s.xs = s.xs[:len(s.xs)-1]
	return v, true
}
''',
"model/emaildomain.go": '''package model

import "strings"

// EmailDomain (t54): part after the last '@'; "" when absent.
func EmailDomain(e string) string {
	i := strings.LastIndex(e, "@")
	if i < 0 {
		return ""
	}
	return e[i+1:]
}
''',
"util/minmax.go": '''package util

// MinInt / MaxInt (t55).
func MinInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func MaxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
''',
"util/sum.go": '''package util

// SumInts / MeanInts (t56); mean uses Go native division, empty -> 0.
func SumInts(xs []int) int {
	t := 0
	for _, x := range xs {
		t += x
	}
	return t
}

func MeanInts(xs []int) int {
	if len(xs) == 0 {
		return 0
	}
	return SumInts(xs) / len(xs)
}
''',
"util/dedupe.go": '''package util

// DedupeStrings (t57): first occurrence wins, order preserved.
func DedupeStrings(xs []string) []string {
	seen := map[string]struct{}{}
	var out []string
	for _, x := range xs {
		if _, ok := seen[x]; ok {
			continue
		}
		seen[x] = struct{}{}
		out = append(out, x)
	}
	return out
}
''',
"util/chunk.go": '''package util

// ChunkStrings (t58): consecutive chunks of n; n <= 0 -> nil.
func ChunkStrings(xs []string, n int) [][]string {
	if n <= 0 {
		return nil
	}
	var out [][]string
	for len(xs) > 0 {
		end := n
		if end > len(xs) {
			end = len(xs)
		}
		out = append(out, xs[:end])
		xs = xs[end:]
	}
	return out
}
''',
"util/percent.go": '''package util

// PercentOf (t59): part*100/whole native division; whole == 0 -> 0.
func PercentOf(part, whole int) int {
	if whole == 0 {
		return 0
	}
	return part * 100 / whole
}
''',
"util/median.go": '''package util

import "sort"

// MedianInt (t60): sorts a copy; even length -> lower middle; empty -> 0.
func MedianInt(xs []int) int {
	if len(xs) == 0 {
		return 0
	}
	c := make([]int, len(xs))
	copy(c, xs)
	sort.Ints(c)
	return c[(len(c)-1)/2]
}
''',
}

def apply_fillers(ws):
    for rel, content in FILLER_FILES.items():
        W(ws, rel, content)

# ---------------- grand ----------------
def apply_all(ws):
    apply_billing(ws)
    apply_users(ws)
    apply_orders(ws)
    apply_store(ws)
    apply_api(ws)
    apply_ids(ws)
    apply_clock(ws)
    apply_fillers(ws)
    # smoke expectation under combined billing: (1000+25) * 1.10 -> 1127
    p = os.path.join(ws, "smoke_test.go")
    src = open(p).read().replace("!= 1100", "!= 1127").replace("want 1100", "want 1127")
    W(ws, "smoke_test.go", src)
