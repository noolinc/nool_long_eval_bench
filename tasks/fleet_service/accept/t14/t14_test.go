package t14

import (
	"encoding/json"
	"testing"
	"net/http/httptest"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestErrorEnvelope(t *testing.T) {
	s := store.NewMem()
	app := &api.App{Users: &service.Users{S: s}, Orders: &service.Orders{S: s}}
	rec := httptest.NewRecorder()
	app.Router().ServeHTTP(rec, httptest.NewRequest("GET", "/users/get?id=missing", nil))
	if rec.Code != 404 {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
	var body struct {
		Error string `json:"error"`
		Code  int    `json:"code"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("body not JSON: %v (%s)", err, rec.Body.String())
	}
	if body.Code != 404 || body.Error == "" {
		t.Fatalf("envelope = %+v, want code 404 and non-empty error", body)
	}
}
