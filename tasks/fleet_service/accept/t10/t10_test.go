package t10

// At subtotal 1000 neither the minimum (t9) nor the waiver (t11) triggers,
// so the expectation is exact regardless of cluster-mates.
import (
	"testing"

	"bench/fleetsvc/service"
)

func TestProcessingFee(t *testing.T) {
	// (1000 + 25) with 10% tax, floored = 1127
	if got := service.Invoice(1000); got != 1127 {
		t.Fatalf("Invoice(1000) = %d, want 1127 (fee 25 before tax)", got)
	}
	if got := service.Invoice(2000); got != 2227 {
		t.Fatalf("Invoice(2000) = %d, want 2227", got)
	}
}
