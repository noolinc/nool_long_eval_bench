package t58

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestChunkStrings(t *testing.T) {
	got := util.ChunkStrings([]string{"a", "b", "c", "d", "e"}, 2)
	if len(got) != 3 || len(got[0]) != 2 || len(got[2]) != 1 || got[2][0] != "e" {
		t.Fatalf("ChunkStrings = %v, want [[a b] [c d] [e]]", got)
	}
	if got := util.ChunkStrings([]string{"a"}, 0); got != nil {
		t.Fatalf("n=0 = %v, want nil", got)
	}
}
