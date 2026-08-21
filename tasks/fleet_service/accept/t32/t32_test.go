package t32

import (
	"encoding/json"
	"testing"

	"bench/fleetsvc/model"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestSkipsNonPositive(t *testing.T) {
	s := store.NewMem()
	orders := &service.Orders{S: s}
	if _, err := orders.Create("u32", 300); err != nil {
		t.Fatalf("Create: %v", err)
	}
	// Injected directly, bypassing Create and any validation it gained.
	neg, _ := json.Marshal(&model.Order{ID: "inj-1", UserID: "u32", Cents: -100})
	zero, _ := json.Marshal(&model.Order{ID: "inj-2", UserID: "u32", Cents: 0})
	s.Put("order/inj-1", neg)
	s.Put("order/inj-2", zero)
	if got := orders.TotalFor("u32"); got != 300 {
		t.Fatalf("TotalFor = %d, want 300 (non-positive records ignored)", got)
	}
}
