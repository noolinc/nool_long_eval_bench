package t19

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestClockHelpers(t *testing.T) {
	util.SetNow(func() int64 { return 5000 })
	defer util.SetNow(func() int64 { return 1000 })
	if got := util.Since(3000); got != 2000 {
		t.Fatalf("Since(3000) = %d, want 2000", got)
	}
	if got := util.Deadline(250); got != 5250 {
		t.Fatalf("Deadline(250) = %d, want 5250", got)
	}
}
