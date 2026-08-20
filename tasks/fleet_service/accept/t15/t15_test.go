package t15

import (
	"testing"

	"bench/fleetsvc/store"
)

func TestLen(t *testing.T) {
	m := store.NewMem()
	if m.Len() != 0 {
		t.Fatalf("empty Len = %d", m.Len())
	}
	m.Put("a", []byte("1"))
	m.Put("b", []byte("2"))
	m.Put("c", []byte("3"))
	if m.Len() != 3 {
		t.Fatalf("Len = %d, want 3", m.Len())
	}
	m.Delete("b")
	if m.Len() != 2 {
		t.Fatalf("Len after delete = %d, want 2", m.Len())
	}
}
