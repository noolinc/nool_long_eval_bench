package t17

import (
	"testing"

	"bench/fleetsvc/store"
)

func TestSnapshotRestore(t *testing.T) {
	m := store.NewMem()
	m.Put("a", []byte("1"))
	snap := m.Snapshot()
	m.Put("b", []byte("2"))
	m.Delete("a")
	m.Restore(snap)
	if _, ok := m.Get("a"); !ok {
		t.Fatal("a must exist after Restore")
	}
	if _, ok := m.Get("b"); ok {
		t.Fatal("b must not exist after Restore")
	}
	// Snapshot must be a deep copy: mutating it must not affect the store.
	snap["a"][0] = 'X'
	if v, _ := m.Get("a"); string(v) == "X" {
		t.Fatal("Snapshot must deep-copy values")
	}
}
