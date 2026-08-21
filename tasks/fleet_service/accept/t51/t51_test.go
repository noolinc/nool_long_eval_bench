package t51

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestStringSet(t *testing.T) {
	s := util.NewStringSet()
	s.Add("a")
	s.Add("b")
	s.Add("a")
	if !s.Has("a") || !s.Has("b") || s.Has("c") {
		t.Fatalf("membership wrong: a=%v b=%v c=%v", s.Has("a"), s.Has("b"), s.Has("c"))
	}
	if got := s.Len(); got != 2 {
		t.Fatalf("Len = %d, want 2", got)
	}
}
