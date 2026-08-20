package service

import (
	"encoding/json"

	"bench/fleetsvc/model"
	"bench/fleetsvc/store"
	"bench/fleetsvc/util"
)

type Orders struct {
	S store.KV
}

func (o *Orders) Create(userID string, cents int) (*model.Order, error) {
	ord := &model.Order{ID: util.NewID("order"), UserID: userID, Cents: cents}
	b, err := json.Marshal(ord)
	if err != nil {
		return nil, err
	}
	o.S.Put("order/"+ord.ID, b)
	return ord, nil
}

func (o *Orders) Get(id string) (*model.Order, error) {
	b, ok := o.S.Get("order/" + id)
	if !ok {
		return nil, ErrNotFound
	}
	var ord model.Order
	if err := json.Unmarshal(b, &ord); err != nil {
		return nil, err
	}
	return &ord, nil
}

// TotalFor sums cents across a user's orders.
func (o *Orders) TotalFor(userID string) int {
	total := 0
	for _, k := range o.S.Keys("order/") {
		b, ok := o.S.Get(k)
		if !ok {
			continue
		}
		var ord model.Order
		if json.Unmarshal(b, &ord) == nil && ord.UserID == userID {
			total += ord.Cents
		}
	}
	return total
}
