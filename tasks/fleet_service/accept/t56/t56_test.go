package t56

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestSumMean(t *testing.T) {
	if got := util.SumInts([]int{1, 2, 3}); got != 6 {
		t.Fatalf("SumInts = %d, want 6", got)
	}
	if got := util.MeanInts([]int{1, 2, 4}); got != 2 {
		t.Fatalf("MeanInts = %d, want 2 (7/3 truncated)", got)
	}
	if got := util.MeanInts([]int{-1, -2}); got != -1 {
		t.Fatalf("MeanInts negatives = %d, want -1 (-3/2 truncated toward zero)", got)
	}
	if s, m := util.SumInts(nil), util.MeanInts(nil); s != 0 || m != 0 {
		t.Fatalf("empty: sum=%d mean=%d, want 0 0", s, m)
	}
}
