package t34

import (
	"testing"

	"bench/fleetsvc/util"
)

// Delta-based so ids issued elsewhere in the process never matter.
func TestIDCount(t *testing.T) {
	base := util.IDCount("t34kind")
	util.NewID("t34kind")
	util.NewID("t34kind")
	util.NewID("t34kind")
	if got := util.IDCount("t34kind"); got != base+3 {
		t.Fatalf("IDCount = %d, want %d", got, base+3)
	}
	if got := util.IDCount("t34-never-issued"); got != 0 {
		t.Fatalf("IDCount(never issued) = %d, want 0", got)
	}
}
