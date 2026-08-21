package t31

import (
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
	"bench/fleetsvc/util"
)

func TestCreatedAt(t *testing.T) {
	util.SetNow(func() int64 { return 424242 })
	defer util.SetNow(func() int64 { return 1000 })

	orders := &service.Orders{S: store.NewMem()}
	o, err := orders.Create("u31", 100)
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	got, err := orders.Get(o.ID)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.CreatedAt != 424242 {
		t.Fatalf("CreatedAt = %d, want 424242 (util.Now at creation)", got.CreatedAt)
	}
}
