package t55

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestMinMax(t *testing.T) {
	if got := util.MinInt(3, 7); got != 3 {
		t.Fatalf("MinInt = %d, want 3", got)
	}
	if got := util.MaxInt(3, 7); got != 7 {
		t.Fatalf("MaxInt = %d, want 7", got)
	}
	if got := util.MinInt(-2, -9); got != -9 {
		t.Fatalf("MinInt negatives = %d, want -9", got)
	}
}
