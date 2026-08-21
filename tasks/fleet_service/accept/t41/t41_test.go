package t41

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestTruncate(t *testing.T) {
	if got := util.Truncate("hello", 3); got != "hel" {
		t.Fatalf("Truncate(hello,3) = %q, want hel", got)
	}
	if got := util.Truncate("hi", 10); got != "hi" {
		t.Fatalf("Truncate(hi,10) = %q, want hi", got)
	}
	if got := util.Truncate("héllo", 2); got != "hé" {
		t.Fatalf("rune truncation = %q, want hé", got)
	}
	if got := util.Truncate("x", 0); got != "" {
		t.Fatalf("Truncate(x,0) = %q, want empty", got)
	}
}
