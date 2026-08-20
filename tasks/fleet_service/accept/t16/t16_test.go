package t16

import (
	"testing"

	"bench/fleetsvc/store"
)

func TestClear(t *testing.T) {
	m := store.NewMem()
	m.Put("a", []byte("1"))
	m.Put("b", []byte("2"))
	m.Clear()
	if got := m.Keys(""); len(got) != 0 {
		t.Fatalf("Keys after Clear = %v, want empty", got)
	}
	if _, ok := m.Get("a"); ok {
		t.Fatal("Get after Clear must miss")
	}
	m.Put("c", []byte("3"))
	if _, ok := m.Get("c"); !ok {
		t.Fatal("store must be usable after Clear")
	}
}
