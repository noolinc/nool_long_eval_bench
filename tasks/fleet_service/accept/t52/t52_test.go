package t52

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestQueue(t *testing.T) {
	q := util.NewQueue()
	q.Push("a")
	q.Push("b")
	if v, ok := q.Pop(); !ok || v != "a" {
		t.Fatalf("first Pop = %q,%v, want a,true", v, ok)
	}
	if v, ok := q.Pop(); !ok || v != "b" {
		t.Fatalf("second Pop = %q,%v, want b,true", v, ok)
	}
	if v, ok := q.Pop(); ok || v != "" {
		t.Fatalf("empty Pop = %q,%v, want \"\",false", v, ok)
	}
}
