package t20

import (
	"sort"
	"testing"

	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestListUsers(t *testing.T) {
	users := &service.Users{S: store.NewMem()}
	for _, e := range []string{"a@x.co", "b@x.co", "c@x.co"} {
		if _, err := users.Create(e); err != nil {
			t.Fatal(err)
		}
	}
	list, err := users.List()
	if err != nil || len(list) != 3 {
		t.Fatalf("List: n=%d err=%v, want 3", len(list), err)
	}
	if !sort.SliceIsSorted(list, func(i, j int) bool { return list[i].ID < list[j].ID }) {
		t.Fatal("List must be sorted by ID ascending")
	}
}
