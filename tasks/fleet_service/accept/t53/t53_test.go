package t53

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestStack(t *testing.T) {
	s := util.NewStack()
	s.Push("a")
	s.Push("b")
	if v, ok := s.Pop(); !ok || v != "b" {
		t.Fatalf("first Pop = %q,%v, want b,true", v, ok)
	}
	if v, ok := s.Pop(); !ok || v != "a" {
		t.Fatalf("second Pop = %q,%v, want a,true", v, ok)
	}
	if _, ok := s.Pop(); ok {
		t.Fatalf("empty Pop ok = true, want false")
	}
}
