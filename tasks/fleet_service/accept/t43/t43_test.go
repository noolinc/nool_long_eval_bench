package t43

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestClampInt(t *testing.T) {
	cases := [][4]int{{5, 1, 10, 5}, {-3, 1, 10, 1}, {42, 1, 10, 10}, {7, 9, 2, 9}}
	for _, c := range cases {
		if got := util.ClampInt(c[0], c[1], c[2]); got != c[3] {
			t.Fatalf("ClampInt(%d,%d,%d) = %d, want %d", c[0], c[1], c[2], got, c[3])
		}
	}
}
