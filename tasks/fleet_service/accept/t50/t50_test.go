package t50

import (
	"testing"

	"bench/fleetsvc/store"
)

func TestCountPrefix(t *testing.T) {
	m := store.NewMem()
	m.Put("a/1", []byte("x"))
	m.Put("a/2", []byte("y"))
	m.Put("b/1", []byte("z"))
	if got := store.CountPrefix(m, "a/"); got != 2 {
		t.Fatalf("CountPrefix(a/) = %d, want 2", got)
	}
	if got := store.CountPrefix(m, "c/"); got != 0 {
		t.Fatalf("CountPrefix(c/) = %d, want 0", got)
	}
}
