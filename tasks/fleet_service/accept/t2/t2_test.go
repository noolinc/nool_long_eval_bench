package t2

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestDiscountedInvoice(t *testing.T) {
	// 1000 - 20% = 800; +10% tax = 880
	if got := service.DiscountedInvoice(1000, 20); got != 880 {
		t.Fatalf("DiscountedInvoice(1000,20) = %d, want 880", got)
	}
	orders := &service.Orders{S: store.NewMem()}
	if _, err := orders.Create("u1", 600); err != nil {
		t.Fatal(err)
	}
	if _, err := orders.Create("u1", 400); err != nil {
		t.Fatal(err)
	}
	if got := orders.TotalWithDiscount("u1", 20); got != 880 {
		t.Fatalf("TotalWithDiscount = %d, want 880", got)
	}
}
