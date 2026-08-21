package t30

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestRejectNonPositive(t *testing.T) {
	s := store.NewMem()
	orders := &service.Orders{S: s}
	if _, err := orders.Create("u30", 0); err == nil {
		t.Fatalf("Create(0) succeeded, want error")
	}
	if _, err := orders.Create("u30", -7); err == nil {
		t.Fatalf("Create(-7) succeeded, want error")
	}
	if n := len(s.Keys("order/")); n != 0 {
		t.Fatalf("%d order(s) stored after rejected creates, want 0", n)
	}
	if _, err := orders.Create("u30", 5); err != nil {
		t.Fatalf("Create(5): %v", err)
	}
}
