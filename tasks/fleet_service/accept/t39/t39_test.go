package t39

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
