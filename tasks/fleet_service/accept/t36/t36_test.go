package t36

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestDisplayName(t *testing.T) {
	u := &model.User{Email: "ada.t36@ex.co"}
	if got := u.DisplayName(); got != "ada.t36" {
		t.Fatalf("DisplayName = %q, want ada.t36", got)
	}
	u2 := &model.User{Email: "no-at-sign"}
	if got := u2.DisplayName(); got != "no-at-sign" {
		t.Fatalf("DisplayName without @ = %q, want whole email", got)
	}
	u3 := &model.User{Email: "@ex.co"}
	if got := u3.DisplayName(); got != "" {
		t.Fatalf("DisplayName with leading @ = %q, want empty", got)
	}
}
