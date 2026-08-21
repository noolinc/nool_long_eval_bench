package t45

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestBackoff(t *testing.T) {
	cases := []struct {
		attempt int
		want    int64
	}{{-1, 100}, {0, 100}, {1, 200}, {3, 800}, {6, 6400}, {7, 10000}, {30, 10000}}
	for _, c := range cases {
		if got := util.Backoff(c.attempt); got != c.want {
			t.Fatalf("Backoff(%d) = %d, want %d", c.attempt, got, c.want)
		}
	}
}
