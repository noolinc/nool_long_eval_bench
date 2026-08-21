package t33

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestValidID(t *testing.T) {
	if id := util.NewID("t33kind"); !util.ValidID(id, "t33kind") {
		t.Fatalf("ValidID(%q, t33kind) = false, want true", id)
	}
	if !util.ValidID("ns/t33kind-12", "t33kind") {
		t.Fatalf("prefixed id rejected, want accepted")
	}
	for _, bad := range []string{"t33kind-", "t33kind", "junk", "t33kind-12x"} {
		if util.ValidID(bad, "t33kind") {
			t.Fatalf("ValidID(%q) = true, want false", bad)
		}
	}
}
