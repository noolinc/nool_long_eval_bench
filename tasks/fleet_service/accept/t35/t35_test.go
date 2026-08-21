package t35

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestKindOf(t *testing.T) {
	if got := util.KindOf(util.NewID("zebra")); got != "zebra" {
		t.Fatalf("KindOf(NewID) = %q, want zebra", got)
	}
	if got := util.KindOf("ns/team/order-7"); got != "order" {
		t.Fatalf("KindOf(prefixed) = %q, want order", got)
	}
	if got := util.KindOf("ab-cd-9"); got != "ab-cd" {
		t.Fatalf("KindOf(multi-dash) = %q, want ab-cd", got)
	}
	for _, bad := range []string{"junk", "kind-", "kind-x9"} {
		if got := util.KindOf(bad); got != "" {
			t.Fatalf("KindOf(%q) = %q, want empty", bad, got)
		}
	}
}
