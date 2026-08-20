package t9

// Property test tolerant of cluster-mates (t10 fee, t11 waiver): at these
// subtotals the minimum dominates whether or not the fee landed.
import (
	"testing"

	"bench/fleetsvc/service"
)

func TestMinimumCharge(t *testing.T) {
	if got := service.Invoice(0); got != 50 {
		t.Fatalf("Invoice(0) = %d, want 50", got)
	}
	if got := service.Invoice(1); got != 50 {
		t.Fatalf("Invoice(1) = %d, want 50", got)
	}
	if got := service.Invoice(10000); got < 10000 {
		t.Fatalf("Invoice(10000) = %d, must not shrink large amounts", got)
	}
}
