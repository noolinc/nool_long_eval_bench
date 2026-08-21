package t24

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
