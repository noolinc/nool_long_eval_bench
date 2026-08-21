package t21

import (
	"testing"

	"bench/fleetsvc/service"
)

// Routed through Invoice itself so any co-landed billing semantics
// (minimum, fee, waiver, cap) apply equally to both sides.
func TestNegativeClamp(t *testing.T) {
	zero := service.Invoice(0)
	for _, s := range []int{-1, -37, -99999} {
		if got := service.Invoice(s); got != zero {
			t.Fatalf("Invoice(%d) = %d, want Invoice(0) = %d", s, got, zero)
		}
	}
}
