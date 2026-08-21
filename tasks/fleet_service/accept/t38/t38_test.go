package t38

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
		t.Fatalf("body = %q (err %v), want {\"status\":\"ok\"}", rec.Body.String(), err)
	}
}
