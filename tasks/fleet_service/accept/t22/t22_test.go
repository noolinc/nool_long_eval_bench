package t22

import (
	"testing"

	"bench/fleetsvc/service"
)

func TestHardCap(t *testing.T) {
	// 20,000,000 exceeds the cap under any co-landed billing rule
	// (with tax ~22M, with the large-order waiver ~20M+fees): always capped.
	if got := service.Invoice(20000000); got != 5000000 {
		t.Fatalf("Invoice(20000000) = %d, want exactly 5000000", got)
	}
	for _, s := range []int{1000, 4000000, 20000000} {
		if got := service.Invoice(s); got > 5000000 {
			t.Fatalf("Invoice(%d) = %d, exceeds cap 5000000", s, got)
		}
	}
}
