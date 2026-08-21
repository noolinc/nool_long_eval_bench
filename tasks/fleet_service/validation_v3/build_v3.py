#!/usr/bin/env python3
"""Build corpus v3: tickets_v3.json (20 carryover + 40 new) and accept tests t21-t60.

Test-design rules (lessons from the two t2 artifacts):
- route both sides of an expectation through the ticket's own functions
  whenever a neighbor ticket could shift shared semantics;
- never pin one reading of an ambiguous spec: pin the edge case in the spec
  text and test exactly that, or accept all valid readings;
- assert only on the ticket's own property, on base routes / fresh stores;
- restore any global state (SetNow, ID namespace) the test touches.
"""
import json, os, tempfile, sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
OUT = os.path.join(tempfile.gettempdir(), "fleetsvc_v3_out")

T = {}   # tid -> (title, [footprint], spec, test_source or None)

# ---------- Cluster A deepen: service/billing.go Invoice body ----------
T["t21"] = ("Negative-subtotal clamp", ["service/billing.go"],
 "Invoice must treat a negative subtotal exactly like a zero subtotal: for any negative input the result equals Invoice(0). Preserve every other behavior of Invoice, including behaviors teammates may be adding in parallel (minimums, fees, tax rules, caps).",
 '''package t21

import (
	"testing"

	"bench/fleetsvc/service"
)

// Routed through Invoice itself so any co-landed billing semantics
// (minimum, fee, waiver, cap) apply equally to both sides.
func TestNegativeClamp(t *testing.T) {
	zero := service.Invoice(0)
	for _, s := range []int{-1, -37, -99999} {
		if got := service.Invoice(s); got != zero {
			t.Fatalf("Invoice(%d) = %d, want Invoice(0) = %d", s, got, zero)
		}
	}
}
''')

T["t22"] = ("Invoice hard cap", ["service/billing.go"],
 "Invoice must never return more than 5000000 cents: any computed amount above that becomes exactly 5000000, applied as the final step after every other rule. Preserve every other behavior of Invoice, including behaviors teammates may be adding in parallel (minimums, fees, tax rules, negative handling).",
 '''package t22

import (
	"testing"

	"bench/fleetsvc/service"
)

func TestHardCap(t *testing.T) {
	// 20,000,000 exceeds the cap under any co-landed billing rule
	// (with tax ~22M, with the large-order waiver ~20M+fees): always capped.
	if got := service.Invoice(20000000); got != 5000000 {
		t.Fatalf("Invoice(20000000) = %d, want exactly 5000000", got)
	}
	for _, s := range []int{1000, 4000000, 20000000} {
		if got := service.Invoice(s); got > 5000000 {
			t.Fatalf("Invoice(%d) = %d, exceeds cap 5000000", s, got)
		}
	}
}
''')

# ---------- Cluster B deepen: api/router.go wrap point ----------
T["t23"] = ("Server identity header", ["api/router.go", "api/handlers.go"],
 "Every response served through Router() must carry the header `X-Served-By: fleetsvc`. Do not modify files outside api/.",
 '''package t23

import (
	"net/http/httptest"
	"net/http"
	"testing"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func app() *api.App {
	return &api.App{Users: &service.Users{S: store.NewMem()}, Orders: &service.Orders{S: store.NewMem()}}
}

// Plain requests to base routes only; status is irrelevant to the property.
func TestServedByHeader(t *testing.T) {
	h := app().Router()
	for _, path := range []string{"/users/get?id=absent", "/users/create?email=t23a@x.co"} {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
		if got := rec.Header().Get("X-Served-By"); got != "fleetsvc" {
			t.Fatalf("GET %s: X-Served-By = %q, want \\"fleetsvc\\"", path, got)
		}
	}
}
''')

T["t24"] = ("Request blocklist", ["api/router.go", "api/handlers.go"],
 "Requests carrying the header `X-Blocked: true` must be rejected by Router() with HTTP status 403 before reaching any handler; all other requests are unaffected. Do not modify files outside api/.",
 '''package t24

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestBlocklist(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	a := &api.App{Users: users, Orders: &service.Orders{S: store.NewMem()}}
	h := a.Router()

	req := httptest.NewRequest(http.MethodGet, "/users/create?email=t24a@x.co", nil)
	req.Header.Set("X-Blocked", "true")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusForbidden {
		t.Fatalf("blocked request: status = %d, want 403", rec.Code)
	}
	if n := len(users.S.Keys("user/")); n != 0 {
		t.Fatalf("blocked request reached the handler: %d user(s) created", n)
	}

	rec2 := httptest.NewRecorder()
	h.ServeHTTP(rec2, httptest.NewRequest(http.MethodGet, "/users/create?email=t24b@x.co", nil))
	if rec2.Code == http.StatusForbidden {
		t.Fatalf("unblocked request rejected with 403")
	}
}
''')

# ---------- Cluster C deepen: store/memstore.go ----------
T["t25"] = ("Store Range iteration", ["store/memstore.go"],
 "Add `func (m *Mem) Range(prefix string, fn func(key string, value []byte) bool)` to store/memstore.go: call fn once per visible entry whose key starts with prefix, in ascending key order, stopping early if fn returns false. Method on Mem only — do NOT change the KV interface.",
 '''package t25

import (
	"testing"

	"bench/fleetsvc/store"
)

func TestRange(t *testing.T) {
	m := store.NewMem()
	m.Put("p/c", []byte("3"))
	m.Put("p/a", []byte("1"))
	m.Put("p/b", []byte("2"))
	m.Put("q/z", []byte("x"))

	var keys []string
	m.Range("p/", func(k string, v []byte) bool { keys = append(keys, k); return true })
	if len(keys) != 3 || keys[0] != "p/a" || keys[1] != "p/b" || keys[2] != "p/c" {
		t.Fatalf("Range order = %v, want [p/a p/b p/c]", keys)
	}

	var n int
	m.Range("p/", func(k string, v []byte) bool { n++; return n < 2 })
	if n != 2 {
		t.Fatalf("early stop visited %d entries, want 2", n)
	}
}
''')

T["t26"] = ("Store value isolation", ["store/memstore.go"],
 "Mem must not alias caller or internal memory: Put stores a copy of the value slice (later mutation of the caller's slice must not change stored data), and Get returns a copy (mutating the returned slice must not change stored data). Preserve all existing method signatures and behavior.",
 '''package t26

import (
	"testing"

	"bench/fleetsvc/store"
)

func TestValueIsolation(t *testing.T) {
	m := store.NewMem()
	v := []byte("abc")
	m.Put("k", v)
	v[0] = 'X'
	got, ok := m.Get("k")
	if !ok || string(got) != "abc" {
		t.Fatalf("after caller mutation: Get = %q, want \\"abc\\"", got)
	}
	got[0] = 'Y'
	got2, _ := m.Get("k")
	if string(got2) != "abc" {
		t.Fatalf("after mutating Get result: Get = %q, want \\"abc\\"", got2)
	}
}
''')

# ---------- Cluster D new: service/users.go Create body ----------
T["t27"] = ("Email lowercasing", ["service/users.go"],
 "Users.Create must lowercase the email before storing it (and before any validation or duplicate checks teammates may be adding); the returned and fetched user's Email is the lowercased input.",
 '''package t27

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestLowercase(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	u, err := users.Create("MiXeD.T27@Example.COM")
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	got, err := users.Get(u.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Email != "mixed.t27@example.com" || u.Email != "mixed.t27@example.com" {
		t.Fatalf("Email stored %q returned %q, want lowercased", got.Email, u.Email)
	}
}
''')

T["t28"] = ("Duplicate email rejection", ["service/users.go"],
 "Users.Create must return an error (any non-nil error) when a user with the same email is already stored, comparing values as stored after any normalization teammates may be adding (lowercasing, trimming); nothing is stored on rejection. Distinct emails must both succeed.",
 '''package t28

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

// Inputs are already normalized (lowercase, no surrounding whitespace) so the
// property holds with or without co-landed normalization tickets.
func TestDuplicateRejected(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	if _, err := users.Create("dup.t28@x.co"); err != nil {
		t.Fatalf("first Create: %v", err)
	}
	if _, err := users.Create("dup.t28@x.co"); err == nil {
		t.Fatalf("second Create with same email succeeded, want error")
	}
	if n := len(users.S.Keys("user/")); n != 1 {
		t.Fatalf("store holds %d users after rejected duplicate, want 1", n)
	}
	if _, err := users.Create("other.t28@x.co"); err != nil {
		t.Fatalf("distinct email rejected: %v", err)
	}
}
''')

T["t29"] = ("Email trimming", ["service/users.go"],
 "Users.Create must trim leading and trailing whitespace (spaces and tabs) from the email before storing it and before any validation, duplicate check, or other normalization; the stored Email carries no surrounding whitespace.",
 '''package t29

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestTrim(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	u, err := users.Create("  trim.t29@y.co\\t")
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	got, err := users.Get(u.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Email != "trim.t29@y.co" {
		t.Fatalf("Email stored %q, want %q", got.Email, "trim.t29@y.co")
	}
}
''')

# ---------- Cluster E new: service/orders.go ----------
T["t30"] = ("Reject non-positive orders", ["service/orders.go"],
 "Orders.Create must return an error (any non-nil error) for cents <= 0 and store nothing; positive amounts are unaffected.",
 '''package t30

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestRejectNonPositive(t *testing.T) {
	s := store.NewMem()
	orders := &service.Orders{S: s}
	if _, err := orders.Create("u30", 0); err == nil {
		t.Fatalf("Create(0) succeeded, want error")
	}
	if _, err := orders.Create("u30", -7); err == nil {
		t.Fatalf("Create(-7) succeeded, want error")
	}
	if n := len(s.Keys("order/")); n != 0 {
		t.Fatalf("%d order(s) stored after rejected creates, want 0", n)
	}
	if _, err := orders.Create("u30", 5); err != nil {
		t.Fatalf("Create(5): %v", err)
	}
}
''')

T["t31"] = ("Order creation timestamp", ["model/order.go", "service/orders.go"],
 "Add a `CreatedAt int64` field to model.Order, set by Orders.Create from util.Now() at creation time, persisted and visible through Orders.Get.",
 '''package t31

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
	"bench/fleetsvc/util"
)

func TestCreatedAt(t *testing.T) {
	util.SetNow(func() int64 { return 424242 })
	defer util.SetNow(func() int64 { return 1000 })

	orders := &service.Orders{S: store.NewMem()}
	o, err := orders.Create("u31", 100)
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	got, err := orders.Get(o.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.CreatedAt != 424242 {
		t.Fatalf("CreatedAt = %d, want 424242 (util.Now at creation)", got.CreatedAt)
	}
}
''')

T["t32"] = ("Defensive totals", ["service/orders.go"],
 "Orders.TotalFor must ignore stored orders whose Cents <= 0 (defensive against records written by paths other than Create); orders with positive Cents sum exactly as before.",
 '''package t32

import (
	"encoding/json"
	"testing"

	"bench/fleetsvc/model"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestSkipsNonPositive(t *testing.T) {
	s := store.NewMem()
	orders := &service.Orders{S: s}
	if _, err := orders.Create("u32", 300); err != nil {
		t.Fatalf("Create: %v", err)
	}
	// Injected directly, bypassing Create and any validation it gained.
	neg, _ := json.Marshal(&model.Order{ID: "inj-1", UserID: "u32", Cents: -100})
	zero, _ := json.Marshal(&model.Order{ID: "inj-2", UserID: "u32", Cents: 0})
	s.Put("order/inj-1", neg)
	s.Put("order/inj-2", zero)
	if got := orders.TotalFor("u32"); got != 300 {
		t.Fatalf("TotalFor = %d, want 300 (non-positive records ignored)", got)
	}
}
''')

# ---------- Cluster F new: util/ids.go ----------
T["t33"] = ("ID validation", ["util/ids.go"],
 "Add `func ValidID(id, kind string) bool` to util/ids.go: true iff id ends with kind + \"-\" + one or more decimal digits; any prefix before that suffix (for example a namespace) is permitted. False otherwise.",
 '''package t33

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestValidID(t *testing.T) {
	if id := util.NewID("t33kind"); !util.ValidID(id, "t33kind") {
		t.Fatalf("ValidID(%q, t33kind) = false, want true", id)
	}
	if !util.ValidID("ns/t33kind-12", "t33kind") {
		t.Fatalf("prefixed id rejected, want accepted")
	}
	for _, bad := range []string{"t33kind-", "t33kind", "junk", "t33kind-12x"} {
		if util.ValidID(bad, "t33kind") {
			t.Fatalf("ValidID(%q) = true, want false", bad)
		}
	}
}
''')

T["t34"] = ("Per-kind ID counting", ["util/ids.go"],
 "Add `func IDCount(kind string) int` to util/ids.go returning how many identifiers NewID has issued for that kind during the current process (0 for kinds never issued). Counting must keep working under any namespace settings teammates may add.",
 '''package t34

import (
	"testing"

	"bench/fleetsvc/util"
)

// Delta-based so ids issued elsewhere in the process never matter.
func TestIDCount(t *testing.T) {
	base := util.IDCount("t34kind")
	util.NewID("t34kind")
	util.NewID("t34kind")
	util.NewID("t34kind")
	if got := util.IDCount("t34kind"); got != base+3 {
		t.Fatalf("IDCount = %d, want %d", got, base+3)
	}
	if got := util.IDCount("t34-never-issued"); got != 0 {
		t.Fatalf("IDCount(never issued) = %d, want 0", got)
	}
}
''')

T["t35"] = ("ID kind extraction", ["util/ids.go"],
 "Add `func KindOf(id string) string` to util/ids.go: for identifiers shaped like NewID output — optionally preceded by a namespace prefix ending in '/' — return the kind: everything after the last '/' (if any) and before the final '-'. Return \"\" when id does not end with '-' followed by one or more digits.",
 '''package t35

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestKindOf(t *testing.T) {
	if got := util.KindOf(util.NewID("zebra")); got != "zebra" {
		t.Fatalf("KindOf(NewID) = %q, want zebra", got)
	}
	if got := util.KindOf("ns/team/order-7"); got != "order" {
		t.Fatalf("KindOf(prefixed) = %q, want order", got)
	}
	if got := util.KindOf("ab-cd-9"); got != "ab-cd" {
		t.Fatalf("KindOf(multi-dash) = %q, want ab-cd", got)
	}
	for _, bad := range []string{"junk", "kind-", "kind-x9"} {
		if got := util.KindOf(bad); got != "" {
			t.Fatalf("KindOf(%q) = %q, want empty", bad, got)
		}
	}
}
''')

# ---------- Cluster G new: model/user.go ----------
T["t36"] = ("User display name", ["model/user.go"],
 "Add `func (u *User) DisplayName() string` to model/user.go: the part of Email before the first '@'; the whole Email when it contains no '@'.",
 '''package t36

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestDisplayName(t *testing.T) {
	u := &model.User{Email: "ada.t36@ex.co"}
	if got := u.DisplayName(); got != "ada.t36" {
		t.Fatalf("DisplayName = %q, want ada.t36", got)
	}
	u2 := &model.User{Email: "no-at-sign"}
	if got := u2.DisplayName(); got != "no-at-sign" {
		t.Fatalf("DisplayName without @ = %q, want whole email", got)
	}
}
''')

T["t37"] = ("User clone", ["model/user.go"],
 "Add `func (u *User) Clone() *User` to model/user.go returning a copy: changes to the clone's fields never affect the original and vice versa. It must copy every field the struct has at build time, including fields teammates may be adding.",
 '''package t37

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestClone(t *testing.T) {
	u := &model.User{ID: "user-1", Email: "c.t37@x.co", Active: true}
	c := u.Clone()
	if c == u {
		t.Fatalf("Clone returned the same pointer")
	}
	c.Email = "changed@x.co"
	c.Active = false
	if u.Email != "c.t37@x.co" || !u.Active {
		t.Fatalf("mutating clone changed original: %+v", u)
	}
}
''')

# ---------- Cluster H new: api endpoints ----------
T["t38"] = ("Health endpoint", ["api/handlers.go", "api/router.go"],
 "Add HTTP endpoint `/health` returning status 200 with JSON body {\"status\": \"ok\"}. Wire it in Router(); do not modify files outside api/.",
 '''package t38

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestHealth(t *testing.T) {
	a := &api.App{Users: &service.Users{S: store.NewMem()}, Orders: &service.Orders{S: store.NewMem()}}
	rec := httptest.NewRecorder()
	a.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/health", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	var body struct{ Status string `json:"status"` }
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil || body.Status != "ok" {
		t.Fatalf("body = %q (err %v), want {\\"status\\":\\"ok\\"}", rec.Body.String(), err)
	}
}
''')

T["t39"] = ("Order total endpoint", ["api/handlers.go", "api/router.go"],
 "Add HTTP endpoint `/orders/total` returning JSON {\"total\": N} with status 200, where N is Orders.TotalFor of the `user_id` query parameter. Wire it in Router(); implement in api/handlers.go; do not modify files outside api/.",
 '''package t39

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

// Expectation routed through Orders.TotalFor itself, so co-landed order
// semantics (validation, defensive totals) apply to both sides.
func TestOrdersTotal(t *testing.T) {
	orders := &service.Orders{S: store.NewMem()}
	a := &api.App{Users: &service.Users{S: store.NewMem()}, Orders: orders}
	if _, err := orders.Create("u39", 600); err != nil {
		t.Fatalf("Create: %v", err)
	}
	if _, err := orders.Create("u39", 400); err != nil {
		t.Fatalf("Create: %v", err)
	}
	want := orders.TotalFor("u39")

	rec := httptest.NewRecorder()
	a.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/orders/total?user_id=u39", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	var body struct{ Total int `json:"total"` }
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil || body.Total != want {
		t.Fatalf("total = %d (err %v), want %d (= TotalFor)", body.Total, err, want)
	}
}
''')

T["t40"] = ("Version endpoint", ["api/handlers.go", "api/router.go"],
 "Add exported `const Version = \"1\"` to api/handlers.go and HTTP endpoint `/version` returning JSON {\"version\": Version} with status 200. Wire it in Router(); do not modify files outside api/.",
 '''package t40

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestVersion(t *testing.T) {
	if api.Version != "1" {
		t.Fatalf("api.Version = %q, want \\"1\\"", api.Version)
	}
	a := &api.App{Users: &service.Users{S: store.NewMem()}, Orders: &service.Orders{S: store.NewMem()}}
	rec := httptest.NewRecorder()
	a.Router().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/version", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	var body struct{ Version string `json:"version"` }
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil || body.Version != api.Version {
		t.Fatalf("version = %q (err %v), want %q", body.Version, err, api.Version)
	}
}
''')

print(f"contended tickets defined: {len(T)}")
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "count":
    sys.exit(0)
