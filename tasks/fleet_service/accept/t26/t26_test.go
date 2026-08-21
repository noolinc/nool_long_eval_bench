package t26

import (
	"testing"

	"bench/fleetsvc/store"
)

func TestValueIsolation(t *testing.T) {
	m := store.NewMem()
	v := []byte("abc")
	m.Put("k", v)
	v[0] = 'X'
	got, ok := m.Get("k")
	if !ok || string(got) != "abc" {
		t.Fatalf("after caller mutation: Get = %q, want \"abc\"", got)
	}
	got[0] = 'Y'
	got2, _ := m.Get("k")
	if string(got2) != "abc" {
		t.Fatalf("after mutating Get result: Get = %q, want \"abc\"", got2)
	}
}
