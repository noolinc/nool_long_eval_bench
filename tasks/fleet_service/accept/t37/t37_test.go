package t37

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestClone(t *testing.T) {
	u := &model.User{ID: "user-1", Email: "c.t37@x.co", Active: true}
	c := u.Clone()
	if c == u {
		t.Fatalf("Clone returned the same pointer")
	}
	c.Email = "changed@x.co"
	c.Active = false
	if u.Email != "c.t37@x.co" || !u.Active {
		t.Fatalf("mutating clone changed original: %+v", u)
	}
}
