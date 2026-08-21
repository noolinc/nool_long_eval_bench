package t27

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestLowercase(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	u, err := users.Create("MiXeD.T27@Example.COM")
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	got, err := users.Get(u.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Email != "mixed.t27@example.com" || u.Email != "mixed.t27@example.com" {
		t.Fatalf("Email stored %q returned %q, want lowercased", got.Email, u.Email)
	}
}
