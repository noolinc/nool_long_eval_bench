package t46

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestSlug(t *testing.T) {
	cases := [][2]string{
		{"Hello, World!", "hello-world"},
		{"  a  b  ", "a-b"},
		{"Go1.21 rocks", "go1-21-rocks"},
		{"---", ""},
	}
	for _, c := range cases {
		if got := util.Slug(c[0]); got != c[1] {
			t.Fatalf("Slug(%q) = %q, want %q", c[0], got, c[1])
		}
	}
}
