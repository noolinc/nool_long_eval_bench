package t1

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestDeactivate(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	u, err := users.Create("a@b.com")
	if err != nil {
		t.Fatal(err)
	}
	if err := users.Deactivate(u.ID); err != nil {
		t.Fatal(err)
	}
	got, err := users.Get(u.ID)
	if err != nil || got.Active {
		t.Fatalf("want inactive user, got %+v err %v", got, err)
	}
	if err := users.Deactivate("user-missing"); err == nil {
		t.Fatal("want error for missing id")
	}
}
