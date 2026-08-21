package t48

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestValidZip(t *testing.T) {
	for _, ok := range []string{"12345", "00000"} {
		if !model.ValidZip(ok) {
			t.Fatalf("ValidZip(%q) = false, want true", ok)
		}
	}
	for _, bad := range []string{"1234", "123456", "12a45", "", "12 45"} {
		if model.ValidZip(bad) {
			t.Fatalf("ValidZip(%q) = true, want false", bad)
		}
	}
}
