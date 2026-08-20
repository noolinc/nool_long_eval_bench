package t6

import (
	"testing"

	"bench/fleetsvc/model"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestValidEmail(t *testing.T) {
	good := []string{"a@b.co", "x.y@z.dev"}
	bad := []string{"", "nope", "a@b", "a b@c.d", "a@@b.c"}
	for _, e := range good {
		if !model.ValidEmail(e) {
			t.Errorf("ValidEmail(%q) = false, want true", e)
		}
	}
	for _, e := range bad {
		if model.ValidEmail(e) {
			t.Errorf("ValidEmail(%q) = true, want false", e)
		}
	}
	s := store.NewMem()
	users := &service.Users{S: s}
	if _, err := users.Create("bad-email"); err == nil {
		t.Fatal("Create must reject invalid email")
	}
	if n := len(s.Keys("user/")); n != 0 {
		t.Fatalf("invalid create must not store; found %d keys", n)
	}
}
