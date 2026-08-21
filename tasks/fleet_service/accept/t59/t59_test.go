package t59

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestPercentOf(t *testing.T) {
	cases := [][3]int{{1, 4, 25}, {2, 3, 66}, {5, 5, 100}, {7, 0, 0}}
	for _, c := range cases {
		if got := util.PercentOf(c[0], c[1]); got != c[2] {
			t.Fatalf("PercentOf(%d,%d) = %d, want %d", c[0], c[1], got, c[2])
		}
	}
}
