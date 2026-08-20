package t7

import (
	"encoding/json"
	"net/http/httptest"
	"testing"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestOrdersCount(t *testing.T) {
	s := store.NewMem()
	app := &api.App{Users: &service.Users{S: s}, Orders: &service.Orders{S: s}}
	for range 2 {
		if _, err := app.Orders.Create("u1", 100); err != nil {
			t.Fatal(err)
		}
	}
	rec := httptest.NewRecorder()
	app.Router().ServeHTTP(rec, httptest.NewRequest("GET", "/orders/count", nil))
	if rec.Code != 200 {
		t.Fatalf("status = %d", rec.Code)
	}
	var body struct{ Count int `json:"count"` }
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil || body.Count != 2 {
		t.Fatalf("body = %s (err %v), want count 2", rec.Body.String(), err)
	}
}
