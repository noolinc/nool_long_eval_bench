package t57

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestDedupeStrings(t *testing.T) {
	got := util.DedupeStrings([]string{"b", "a", "b", "c", "a"})
	if len(got) != 3 || got[0] != "b" || got[1] != "a" || got[2] != "c" {
		t.Fatalf("DedupeStrings = %v, want [b a c]", got)
	}
	if got := util.DedupeStrings(nil); len(got) != 0 {
		t.Fatalf("DedupeStrings(nil) = %v, want length 0", got)
	}
}
