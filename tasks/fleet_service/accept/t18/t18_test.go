package t18

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestOrderStatus(t *testing.T) {
	orders := &service.Orders{S: store.NewMem()}
	ord, err := orders.Create("u1", 100)
	if err != nil {
		t.Fatal(err)
	}
	if err := orders.SetStatus(ord.ID, "shipped"); err != nil {
		t.Fatal(err)
	}
	got, err := orders.Get(ord.ID)
	if err != nil || got.Status != "shipped" {
		t.Fatalf("Status = %q err %v, want shipped", got.Status, err)
	}
	if err := orders.SetStatus("order-missing", "x"); err == nil {
		t.Fatal("want error for missing order")
	}
}
