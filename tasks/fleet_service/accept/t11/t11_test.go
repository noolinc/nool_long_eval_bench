package t11

// Range assertion tolerant of the fee ticket (t10): no 10% tax may be
// applied at or above 100000, but a small fixed fee is acceptable.
import (
	"testing"

	"bench/fleetsvc/service"
)

func TestTaxWaiver(t *testing.T) {
	got := service.Invoice(200000)
	if got < 200000 || got > 200100 {
		t.Fatalf("Invoice(200000) = %d, want [200000,200100] (no tax; small fee ok)", got)
	}
	got = service.Invoice(100000)
	if got < 100000 || got > 100100 {
		t.Fatalf("Invoice(100000) = %d, want [100000,100100]", got)
	}
	if got := service.Invoice(50000); got < 55000 {
		t.Fatalf("Invoice(50000) = %d, tax must still apply below threshold", got)
	}
}
