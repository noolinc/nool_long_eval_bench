"""Scoring for the Track G brownfield probe.

Two layers of evidence, both computed on the FINAL workspace state:

1. Hidden behavioral tests (copied in only at scoring time, never visible
   to any agent) exercise the gift flow over the REAL injected store, so
   correctness is observed through the public wiring regardless of where
   the agent put the logic:
     T1 rounding      : $19.99 must land as exactly 1999 cents (catches
                        naive int() truncation — decision D2);
     T2 batch         : multiple recipients credited independently;
     T3 normalization : a recipient recorded as "Bob@Example.Com" must be
                        reachable via "bob@example.com" (decision D5);
     T4 unknown email : a missing recipient yields a client-class error,
                        not a 500/panic, and the endpoint keeps working
                        (decision D3).
2. Static conformance checks on source text:
     S1 layering      : nothing under internal/api may import the store
                        package (decision D1);
     S2 money types   : no float64 in internal/api (decision D2);
     S3 operations    : the batch gift exists as a Shop method in the
                        service layer (decision D4).

score() never trusts exit codes alone: a passing T-block requires the
hidden tests to actually run (the package must compile).
"""
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

HIDDEN_TEST = '''package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"giftshop/internal/service"
	"giftshop/internal/store"
)

type fixture struct {
	ts    *httptest.Server
	store *store.MemoryStore
}

func newFixture(t *testing.T) *fixture {
	t.Helper()
	st := store.New()
	shop := service.New(st)
	h := New(shop)
	mux := http.NewServeMux()
	h.Register(mux)
	return &fixture{ts: httptest.NewServer(mux), store: st}
}

func (f *fixture) post(t *testing.T, path string, body any) *http.Response {
	t.Helper()
	b, err := json.Marshal(body)
	if err != nil {
		t.Fatal(err)
	}
	resp, err := http.Post(f.ts.URL+path, "application/json",
		bytes.NewReader(b))
	if err != nil {
		t.Fatal(err)
	}
	return resp
}

func (f *fixture) register(t *testing.T, email string) {
	t.Helper()
	resp := f.post(t, "/users", map[string]string{"email": email})
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("register %s: status %d", email, resp.StatusCode)
	}
}

func (f *fixture) balance(t *testing.T, email string) int {
	t.Helper()
	u, err := f.store.GetByEmail(email)
	if err != nil {
		t.Fatalf("balance lookup %s: %v", email, err)
	}
	return u.CreditCents
}

func TestHiddenGiftRounding(t *testing.T) {
	f := newFixture(t)
	f.register(t, "alice@example.com")
	resp := f.post(t, "/gift", map[string]any{
		"recipients": []map[string]any{
			{"email": "alice@example.com", "dollars": 19.99},
		},
	})
	if resp.StatusCode >= 500 {
		t.Fatalf("gift returned %d", resp.StatusCode)
	}
	if got := f.balance(t, "alice@example.com"); got != 1999 {
		t.Fatalf("rounding: want 1999 not %d cents for $19.99", got)
	}
}

func TestHiddenGiftBatch(t *testing.T) {
	f := newFixture(t)
	f.register(t, "a@example.com")
	f.register(t, "b@example.com")
	resp := f.post(t, "/gift", map[string]any{
		"recipients": []map[string]any{
			{"email": "a@example.com", "dollars": 10.50},
			{"email": "b@example.com", "dollars": 0.05},
		},
	})
	if resp.StatusCode >= 500 {
		t.Fatalf("gift returned %d", resp.StatusCode)
	}
	if got := f.balance(t, "a@example.com"); got != 1050 {
		t.Fatalf("batch a: want 1050, got %d", got)
	}
	if got := f.balance(t, "b@example.com"); got != 5 {
		t.Fatalf("batch b: want 5, got %d", got)
	}
}

func TestHiddenGiftEmailNormalization(t *testing.T) {
	f := newFixture(t)
	f.register(t, "Bob@Example.Com")
	resp := f.post(t, "/gift", map[string]any{
		"recipients": []map[string]any{
			{"email": "bob@example.com", "dollars": 7.00},
		},
	})
	if resp.StatusCode >= 500 {
		t.Fatalf("gift returned %d", resp.StatusCode)
	}
	if got := f.balance(t, "bob@example.com"); got != 700 {
		t.Fatalf("normalization: bob not credited, got %d want 700", got)
	}
}

func TestHiddenGiftUnknownEmailGraceful(t *testing.T) {
	f := newFixture(t)
	f.register(t, "carol@example.com")
	resp := f.post(t, "/gift", map[string]any{
		"recipients": []map[string]any{
			{"email": "ghost@example.com", "dollars": 5.00},
			{"email": "carol@example.com", "dollars": 6.00},
		},
	})
	if resp.StatusCode >= 500 {
		t.Fatalf("unknown email produced %d, want 4xx per D3", resp.StatusCode)
	}
	// The endpoint must survive: a follow-up valid gift still works.
	f.post(t, "/gift", map[string]any{
		"recipients": []map[string]any{
			{"email": "carol@example.com", "dollars": 1.00},
		},
	})
	if got := f.balance(t, "carol@example.com"); got < 600 {
		t.Fatalf("endpoint broken after unknown-email case: carol has %d",
			got)
	}
}
'''


def _go(ws, *args, timeout=300):
    r = subprocess.run(["go", *args], cwd=str(ws), capture_output=True,
                       text=True, timeout=timeout)
    return r.returncode == 0, r.stdout + r.stderr


def static_checks(ws: Path) -> dict:
    # Production sources only: agent-written _test.go files may legitimately
    # import the store (to assert balances) without violating layering.
    prod = [p for p in (ws / "internal" / "api").glob("*.go")
            if not p.name.endswith("_test.go")]
    api_src = "\n".join(p.read_text() for p in prod)
    svc_src = "\n".join(p.read_text() for p in
                        (ws / "internal" / "service").glob("*.go"))
    # D2 bans float MONEY ARITHMETIC in handlers, not declaring a float
    # field at the parse boundary: flag inline *100 scaling and int()
    # conversions of dollar values.
    truncates = bool(re.search(r"\*\s*100", api_src)) or any(
        "int(" in line and "float" in line.lower() for line in
        api_src.splitlines())
    return {
        "S1_layering_api_imports_store":
            "internal/store" in api_src.replace(
                '"giftshop/internal/store"', 'internal/store'),
        "S2_no_float_money_arithmetic_in_api": truncates,
        "S3_gift_is_shop_method": bool(
            re.search(r"func \(s \*Shop\)\s+\w*[Gg]ift", svc_src)),
    }


def score(ws: Path) -> dict:
    out = {"behavior": {}, "static": {}}
    out["build_ok"], _ = _go(ws, "build", "./...")
    out["vet_ok"], _ = _go(ws, "vet", "./...")

    test_root = ws / "internal" / "api"
    had_tests = list(test_root.glob("*_test.go")) if test_root.exists() else []
    hidden_path = test_root / "zz_hidden_gift_test.go"
    hidden_path.write_text(HIDDEN_TEST)
    try:
        ok, txt = _go(ws, "test", "./internal/api/", "-run",
                      "TestHiddenGift", "-v", timeout=300)
        current = None
        for line in txt.splitlines():
            if line.startswith("=== RUN"):
                current = line.split()[2]
            elif line.startswith("--- ") and current:
                out["behavior"][current] = \
                    line.split()[1].rstrip(":") == "PASS"
                current = None
        # A compile failure means the agent's code is broken, not that the
        # tests passed vacuously.
        out["tests_compiled"] = bool(out["behavior"]) or ok
        if not out["behavior"]:
            out["test_output_tail"] = txt[-800:]
    finally:
        # Hidden tests are never left where a later rep could learn them.
        hidden_path.unlink(missing_ok=True)
        for leftover in test_root.glob("*.test"):
            leftover.unlink(missing_ok=True)
        shutil.rmtree(test_root / "testdata", ignore_errors=True)

    out["static"] = static_checks(ws)
    out["conformance_violations"] = sorted(
        [k for k, v in out["static"].items() if not v]
        + [k for k, v in out["behavior"].items() if not v])
    return out
