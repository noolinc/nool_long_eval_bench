package t12

import (
	"strings"
	"testing"
	"net/http/httptest"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestRequestIDHeader(t *testing.T) {
	s := store.NewMem()
	app := &api.App{Users: &service.Users{S: s}, Orders: &service.Orders{S: s}}
	r := app.Router()
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, httptest.NewRequest("GET", "/users/get?id=nope", nil))
	id1 := rec.Header().Get("X-Request-Id")
	if id1 == "" || !strings.Contains(id1, "req") {
		t.Fatalf("X-Request-Id = %q, want fresh req id", id1)
	}
	rec2 := httptest.NewRecorder()
	r.ServeHTTP(rec2, httptest.NewRequest("GET", "/users/get?id=nope", nil))
	if id2 := rec2.Header().Get("X-Request-Id"); id2 == "" || id2 == id1 {
		t.Fatalf("second X-Request-Id = %q, must be fresh (first %q)", id2, id1)
	}
}
