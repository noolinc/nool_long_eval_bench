package t8

import (
	"strings"
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
	"bench/fleetsvc/util"
)

func TestIDNamespace(t *testing.T) {
	util.SetIDNamespace("prod")
	defer util.SetIDNamespace("")
	id := util.NewID("thing")
	if !strings.HasPrefix(id, "prod/thing-") {
		t.Fatalf("NewID = %q, want prod/thing-<n>", id)
	}
	users := &service.Users{S: store.NewMem()}
	u, err := users.Create("a@b.co")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(u.ID, "prod/user-") {
		t.Fatalf("user ID = %q, want prod/user-<n>", u.ID)
	}
	if got, err := users.Get(u.ID); err != nil || got.ID != u.ID {
		t.Fatalf("round trip under namespace failed: %v %v", got, err)
	}
	util.SetIDNamespace("")
	if strings.Contains(util.NewID("x"), "/") {
		t.Fatal("empty namespace must restore default form")
	}
}
