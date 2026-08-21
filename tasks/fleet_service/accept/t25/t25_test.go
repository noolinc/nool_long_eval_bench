package t25

import (
	"testing"

	"bench/fleetsvc/store"
)

func TestRange(t *testing.T) {
	m := store.NewMem()
	m.Put("p/c", []byte("3"))
	m.Put("p/a", []byte("1"))
	m.Put("p/b", []byte("2"))
	m.Put("q/z", []byte("x"))

	var keys []string
	m.Range("p/", func(k string, v []byte) bool { keys = append(keys, k); return true })
	if len(keys) != 3 || keys[0] != "p/a" || keys[1] != "p/b" || keys[2] != "p/c" {
		t.Fatalf("Range order = %v, want [p/a p/b p/c]", keys)
	}

	var n int
	m.Range("p/", func(k string, v []byte) bool { n++; return n < 2 })
	if n != 2 {
		t.Fatalf("early stop visited %d entries, want 2", n)
	}
}
