package t40

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
		t.Fatalf("api.Version = %q, want \"1\"", api.Version)
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
