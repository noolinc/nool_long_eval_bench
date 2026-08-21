package t2

// Property test tolerant of cluster-A billing changes (t9 minimum, t10 fee,
// t11 waiver): every expectation routes both sides through the ticket's own
// functions, so it tracks whatever Invoice semantics are on main instead of
// hard-coding pre-cluster totals. Corpus v2.2: the v2 version hard-coded 880
// and failed whenever t10's fee had landed; the v2.1 version pinned one of
// two valid floor readings of the spec and failed every implementation that
// chose the other. The rounding check now admits both readings.
import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestDiscountedInvoice(t *testing.T) {
	// 20% off 1000 must equal invoicing the discounted subtotal directly.
	if got, want := service.DiscountedInvoice(1000, 20), service.DiscountedInvoice(800, 0); got != want {
		t.Fatalf("DiscountedInvoice(1000,20) = %d, want %d (= DiscountedInvoice(800,0))", got, want)
	}
	// Round-down: the spec does not pin whether the floor applies to the
	// discounted subtotal (999*80/100 = 799) or to the discount amount
	// (999 - 999*20/100 = 800); accept either, routed through the ticket's
	// own function so cluster-A billing changes stay tolerated.
	gotR := service.DiscountedInvoice(999, 20)
	if a, b := service.DiscountedInvoice(799, 0), service.DiscountedInvoice(800, 0); gotR != a && gotR != b {
		t.Fatalf("DiscountedInvoice(999,20) = %d, want %d or %d (either floor reading)", gotR, a, b)
	}
	// A 20%% discount must strictly reduce a mid-size invoice.
	if full, disc := service.DiscountedInvoice(1000, 0), service.DiscountedInvoice(1000, 20); disc >= full {
		t.Fatalf("DiscountedInvoice(1000,20) = %d, not below undiscounted %d", disc, full)
	}
}

func TestTotalWithDiscount(t *testing.T) {
	orders := &service.Orders{S: store.NewMem()}
	if _, err := orders.Create("u1", 600); err != nil {
		t.Fatal(err)
	}
	if _, err := orders.Create("u1", 400); err != nil {
		t.Fatal(err)
	}
	if got, want := orders.TotalWithDiscount("u1", 20), service.DiscountedInvoice(1000, 20); got != want {
		t.Fatalf("TotalWithDiscount(u1,20) = %d, want %d (= DiscountedInvoice(TotalFor(u1),20))", got, want)
	}
}
