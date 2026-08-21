package t54

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestEmailDomain(t *testing.T) {
	cases := [][2]string{
		{"a@b.co", "b.co"},
		{"weird@@x.io", "x.io"},
		{"nodomain", ""},
		{"trail@", ""},
	}
	for _, c := range cases {
		if got := model.EmailDomain(c[0]); got != c[1] {
			t.Fatalf("EmailDomain(%q) = %q, want %q", c[0], got, c[1])
		}
	}
}
