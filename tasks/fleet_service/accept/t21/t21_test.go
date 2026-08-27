package t21

import (
	"testing"

	"bench/fleetsvc/service"
)

func TestNegativeRejected(t *testing.T) {
	for _, s := range []int{-1, -37, -99999} {
		if got := service.Invoice(s); got != 0 {
			t.Fatalf("Invoice(%d) = %d, want 0", s, got)
		}
	}
}
