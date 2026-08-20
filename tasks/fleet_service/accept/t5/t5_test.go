package t5

import (
	"strings"
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
	"bench/fleetsvc/util"
)

func TestAudit(t *testing.T) {
	before := len(util.AuditLog())
	orders := &service.Orders{S: store.NewMem()}
	ord, err := orders.Create("u1", 100)
	if err != nil {
		t.Fatal(err)
	}
	log := util.AuditLog()
	if len(log) != before+1 {
		t.Fatalf("audit log grew by %d, want 1", len(log)-before)
	}
	last := log[len(log)-1]
	if !strings.HasPrefix(last, "order.created ") || !strings.Contains(last, ord.ID) {
		t.Fatalf("last audit entry = %q", last)
	}
}
