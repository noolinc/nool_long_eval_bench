package t44

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestAbsInt(t *testing.T) {
	for _, c := range [][2]int{{5, 5}, {-5, 5}, {0, 0}} {
		if got := util.AbsInt(c[0]); got != c[1] {
			t.Fatalf("AbsInt(%d) = %d, want %d", c[0], got, c[1])
		}
	}
}
