package t2

// Property test tolerant of cluster-A billing changes (t9 minimum, t10 fee,
// t11 waiver): every expectation routes both sides through the ticket's own
// functions, so it tracks whatever Invoice semantics are on main instead of
// hard-coding pre-cluster totals. Corpus v2.1 hardening; the v2 version of
// this test hard-coded 880 and failed whenever t10's fee had landed.
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
	// Round-down: 999 at 20%% floors to 799 before tax.
	if got, want := service.DiscountedInvoice(999, 20), service.DiscountedInvoice(799, 0); got != want {
		t.Fatalf("DiscountedInvoice(999,20) = %d, want %d (floor to 799, then invoice)", got, want)
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
