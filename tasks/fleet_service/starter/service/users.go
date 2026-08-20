package service

import (
	"encoding/json"
	"errors"

	"bench/fleetsvc/model"
	"bench/fleetsvc/store"
	"bench/fleetsvc/util"
)

var ErrNotFound = errors.New("not found")

type Users struct {
	S store.KV
}

func (u *Users) Create(email string) (*model.User, error) {
	usr := &model.User{ID: util.NewID("user"), Email: email, Active: true}
	b, err := json.Marshal(usr)
	if err != nil {
		return nil, err
	}
	u.S.Put("user/"+usr.ID, b)
	return usr, nil
}

func (u *Users) Get(id string) (*model.User, error) {
	b, ok := u.S.Get("user/" + id)
	if !ok {
		return nil, ErrNotFound
	}
	var usr model.User
	if err := json.Unmarshal(b, &usr); err != nil {
		return nil, err
	}
	return &usr, nil
}
