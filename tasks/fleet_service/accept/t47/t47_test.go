package t47

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestFormatCents(t *testing.T) {
	cases := []struct {
		c    int
		want string
	}{{1234, "12.34"}, {5, "0.05"}, {0, "0.00"}, {-5, "-0.05"}, {-1234, "-12.34"}, {100, "1.00"}}
	for _, c := range cases {
		if got := model.FormatCents(c.c); got != c.want {
			t.Fatalf("FormatCents(%d) = %q, want %q", c.c, got, c.want)
		}
	}
}
