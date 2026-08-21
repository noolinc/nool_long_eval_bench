package t49

import (
	"sync"
	"testing"

	"bench/fleetsvc/store"
)

func TestCounter(t *testing.T) {
	c := store.NewCounter()
	if got := c.Inc(); got != 1 {
		t.Fatalf("first Inc = %d, want 1", got)
	}
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); c.Inc() }()
	}
	wg.Wait()
	if got := c.Value(); got != 51 {
		t.Fatalf("Value = %d, want 51", got)
	}
}
