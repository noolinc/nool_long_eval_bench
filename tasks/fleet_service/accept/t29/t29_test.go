package t29

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestTrim(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	u, err := users.Create("  trim.t29@y.co\t")
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	got, err := users.Get(u.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.Email != "trim.t29@y.co" {
		t.Fatalf("Email stored %q, want %q", got.Email, "trim.t29@y.co")
	}
}
