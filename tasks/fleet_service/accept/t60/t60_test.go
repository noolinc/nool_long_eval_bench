package t60

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestMedianInt(t *testing.T) {
	if got := util.MedianInt([]int{5, 1, 3}); got != 3 {
		t.Fatalf("odd median = %d, want 3", got)
	}
	if got := util.MedianInt([]int{4, 1, 3, 2}); got != 2 {
		t.Fatalf("even median = %d, want 2 (lower middle)", got)
	}
	if got := util.MedianInt(nil); got != 0 {
		t.Fatalf("empty median = %d, want 0", got)
	}
	in := []int{9, 1}
	util.MedianInt(in)
	if in[0] != 9 || in[1] != 1 {
		t.Fatalf("input mutated: %v", in)
	}
}
