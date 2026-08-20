package main_test

// Smoke suite: guards base behavior. Visible to agents; must stay green
// after every ticket. Ticket acceptance tests are separate and hidden.

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestUserRoundTrip(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	u, err := users.Create("a@example.com")
	if err != nil {
		t.Fatal(err)
	}
	got, err := users.Get(u.ID)
	if err != nil || got.Email != "a@example.com" || !got.Active {
		t.Fatalf("round trip failed: %v %v", got, err)
	}
}

func TestOrderTotals(t *testing.T) {
	s := store.NewMem()
	orders := &service.Orders{S: s}
	u := "user-x"
	if _, err := orders.Create(u, 250); err != nil {
		t.Fatal(err)
	}
	if _, err := orders.Create(u, 750); err != nil {
		t.Fatal(err)
	}
	if got := orders.TotalFor(u); got != 1000 {
		t.Fatalf("TotalFor = %d, want 1000", got)
	}
	if got := service.Invoice(1000); got != 1100 {
		t.Fatalf("Invoice(1000) = %d, want 1100", got)
	}
}
