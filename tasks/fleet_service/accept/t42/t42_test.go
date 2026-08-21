package t42

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestReverseString(t *testing.T) {
	if got := util.ReverseString("abc"); got != "cba" {
		t.Fatalf("ReverseString(abc) = %q, want cba", got)
	}
	if got := util.ReverseString(util.ReverseString("héllo")); got != "héllo" {
		t.Fatalf("double reverse = %q, want héllo", got)
	}
	if got := util.ReverseString(""); got != "" {
		t.Fatalf("ReverseString(empty) = %q, want empty", got)
	}
}
