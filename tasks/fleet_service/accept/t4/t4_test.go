package t4

import (
	"testing"

	"bench/fleetsvc/store"
	"bench/fleetsvc/util"
)

func TestTTL(t *testing.T) {
	util.SetNow(func() int64 { return 1000 })
	m := store.NewMem()
	m.PutTTL("a", []byte("x"), 1500)
	m.Put("b", []byte("y"))
	if _, ok := m.Get("a"); !ok {
		t.Fatal("a should be visible before expiry")
	}
	util.SetNow(func() int64 { return 1500 })
	if _, ok := m.Get("a"); ok {
		t.Fatal("a should be expired at exactly expiresAt (Now() >= expiresAt)")
	}
	util.SetNow(func() int64 { return 2000 })
	if _, ok := m.Get("a"); ok {
		t.Fatal("a should be expired")
	}
	if got := m.Keys(""); len(got) != 1 || got[0] != "b" {
		t.Fatalf("Keys = %v, want [b]", got)
	}
	if _, ok := m.Get("b"); !ok {
		t.Fatal("plain Put must never expire")
	}
	util.SetNow(func() int64 { return 1000 })
}
