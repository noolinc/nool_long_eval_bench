package t23

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
			t.Fatalf("GET %s: X-Served-By = %q, want \"fleetsvc\"", path, got)
		}
	}
}
