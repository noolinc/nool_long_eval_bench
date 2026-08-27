#!/usr/bin/env python3
"""Subset-parametrized reference generator for the users cluster (corpus v3).

emit(ws, enabled) writes service/users.go and model/user.go implementing
exactly the tickets in `enabled`; disabled tickets keep starter semantics.
emit(ws, set(TICKETS)) is byte-identical to refs.apply_users(ws) output.
Drop-in replacement for refs.apply_users in the canonical apply order
(billing, users, orders, store, api, ids, clock, fillers).
"""
import os

TICKETS = ["t1", "t6", "t20", "t27", "t28", "t29", "t36", "t37"]


def _w(ws, rel, content):
    p = os.path.join(ws, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)


# ---------------- model/user.go ----------------

_MODEL_STRUCT = '''type User struct {
	ID     string
	Email  string
	Active bool
}
'''

_MODEL_T6 = '''
// ValidEmail (t6): exactly one '@', at least one '.' after it, no spaces.
func ValidEmail(e string) bool {
	if strings.Count(e, "@") != 1 || strings.ContainsAny(e, " \\t") {
		return false
	}
	at := strings.Index(e, "@")
	return strings.Contains(e[at+1:], ".")
}
'''

_MODEL_T36 = '''
// DisplayName (t36): part of Email before the first '@'.
func (u *User) DisplayName() string {
	if i := strings.Index(u.Email, "@"); i >= 0 {
		return u.Email[:i]
	}
	return u.Email
}
'''

_MODEL_T37 = '''
// Clone (t37): field-complete copy.
func (u *User) Clone() *User {
	c := *u
	return &c
}
'''


def _model_user_go(on):
    parts = ["package model\n"]
    if "t6" in on or "t36" in on:
        parts.append('\nimport "strings"\n')
    parts.append("\n")
    parts.append(_MODEL_STRUCT)
    if "t6" in on:
        parts.append(_MODEL_T6)
    if "t36" in on:
        parts.append(_MODEL_T36)
    if "t37" in on:
        parts.append(_MODEL_T37)
    return "".join(parts)


# ---------------- service/users.go ----------------

_USERS_CREATE_T29 = '\temail = strings.TrimSpace(email)  // t29: trim first\n'
_USERS_CREATE_T27 = '\temail = strings.ToLower(email)    // t27: then lowercase\n'
_USERS_CREATE_T6 = '''\tif !model.ValidEmail(email) {     // t6
		return nil, errors.New("invalid email")
	}
'''
_USERS_CREATE_T28 = '''\tfor _, k := range u.S.Keys("user/") { // t28: duplicate check on stored form
		b, ok := u.S.Get(k)
		if !ok {
			continue
		}
		var ex model.User
		if json.Unmarshal(b, &ex) == nil && ex.Email == email {
			return nil, errors.New("duplicate email")
		}
	}
'''

_USERS_CREATE_TAIL = '''\tusr := &model.User{ID: util.NewID("user"), Email: email, Active: true}
	b, err := json.Marshal(usr)
	if err != nil {
		return nil, err
	}
	u.S.Put("user/"+usr.ID, b)
	return usr, nil
}
'''

_USERS_GET = '''
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
'''

_USERS_T1 = '''
// Deactivate (t1).
func (u *Users) Deactivate(id string) error {
	usr, err := u.Get(id)
	if err != nil {
		return err
	}
	usr.Active = false
	b, err := json.Marshal(usr)
	if err != nil {
		return err
	}
	u.S.Put("user/"+usr.ID, b)
	return nil
}
'''

_USERS_T20 = '''
// List (t20): all users sorted by ID ascending.
func (u *Users) List() ([]*model.User, error) {
	var out []*model.User
	for _, k := range u.S.Keys("user/") {
		b, ok := u.S.Get(k)
		if !ok {
			continue
		}
		var usr model.User
		if err := json.Unmarshal(b, &usr); err != nil {
			return nil, err
		}
		out = append(out, &usr)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })
	return out, nil
}
'''


def _service_users_go(on):
    std = ['\t"encoding/json"\n', '\t"errors"\n']
    if "t20" in on:
        std.append('\t"sort"\n')
    if "t27" in on or "t29" in on:
        std.append('\t"strings"\n')
    parts = ["package service\n\nimport (\n"]
    parts.extend(std)
    parts.append('\n\t"bench/fleetsvc/model"\n')
    parts.append('\t"bench/fleetsvc/store"\n')
    parts.append('\t"bench/fleetsvc/util"\n)\n')
    parts.append('''
var ErrNotFound = errors.New("not found")

type Users struct {
	S store.KV
}

func (u *Users) Create(email string) (*model.User, error) {
''')
    if "t29" in on:
        parts.append(_USERS_CREATE_T29)
    if "t27" in on:
        parts.append(_USERS_CREATE_T27)
    if "t6" in on:
        parts.append(_USERS_CREATE_T6)
    if "t28" in on:
        parts.append(_USERS_CREATE_T28)
    parts.append(_USERS_CREATE_TAIL)
    parts.append(_USERS_GET)
    if "t1" in on:
        parts.append(_USERS_T1)
    if "t20" in on:
        parts.append(_USERS_T20)
    return "".join(parts)


def emit(ws, enabled):
    on = set(enabled)
    unknown = on - set(TICKETS)
    if unknown:
        raise ValueError("unknown users tickets: %s" % sorted(unknown))
    _w(ws, "service/users.go", _service_users_go(on))
    _w(ws, "model/user.go", _model_user_go(on))
