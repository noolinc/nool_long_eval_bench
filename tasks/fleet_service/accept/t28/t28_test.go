package t28

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

// Inputs are already normalized (lowercase, no surrounding whitespace) so the
// property holds with or without co-landed normalization tickets.
func TestDuplicateRejected(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	if _, err := users.Create("dup.t28@x.co"); err != nil {
		t.Fatalf("first Create: %v", err)
	}
	if _, err := users.Create("dup.t28@x.co"); err == nil {
		t.Fatalf("second Create with same email succeeded, want error")
	}
	if n := len(users.S.Keys("user/")); n != 1 {
		t.Fatalf("store holds %d users after rejected duplicate, want 1", n)
	}
	if _, err := users.Create("other.t28@x.co"); err != nil {
		t.Fatalf("distinct email rejected: %v", err)
	}
}
