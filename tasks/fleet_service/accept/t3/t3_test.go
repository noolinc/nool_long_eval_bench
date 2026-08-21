package t3

import (
	"encoding/json"
	"net/http/httptest"
	"testing"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestUsersCount(t *testing.T) {
	s := store.NewMem()
	app := &api.App{Users: &service.Users{S: s}, Orders: &service.Orders{S: s}}
	// Distinct emails: the property under test is the count endpoint, and
	// duplicate-rejection semantics teammates may add must not interfere.
	for _, e := range []string{"x1@y.com", "x2@y.com", "x3@y.com"} {
		if _, err := app.Users.Create(e); err != nil {
			t.Fatal(err)
		}
	}
	rec := httptest.NewRecorder()
	app.Router().ServeHTTP(rec, httptest.NewRequest("GET", "/users/count", nil))
	if rec.Code != 200 {
		t.Fatalf("status = %d", rec.Code)
	}
	var body struct{ Count int `json:"count"` }
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil || body.Count != 3 {
		t.Fatalf("body = %s (err %v), want count 3", rec.Body.String(), err)
	}
}
