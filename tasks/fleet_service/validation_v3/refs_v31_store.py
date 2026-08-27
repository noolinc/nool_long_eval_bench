#!/usr/bin/env python3
"""Subset-parametrized reference generator for the store cluster (corpus v3).

emit(ws, enabled) writes store/kv.go and store/memstore.go implementing
exactly the tickets in `enabled`; disabled tickets keep starter semantics
(the empty subset reproduces both starter files byte-for-byte).
emit(ws, set(TICKETS)) is byte-identical to refs.apply_store(ws) output.
Drop-in replacement for refs.apply_store in the canonical apply order
(billing, users, orders, store, api, ids, clock, fillers).

Layout notes: t4 switches Mem's representation from map[string][]byte to
map[string]entry (val + exp) and gates every visibility check; the cp
helper is emitted whenever an enabled ticket copies bytes (t26 value
isolation, t17's deep-copy Snapshot/Restore, t25's Range handing values
to the callback outside the lock). t4's TTL reads util.Now, which the
starter util/clock.go already provides, so no dependency on the t19
clock cluster (applied after store in the canonical order).
"""
import os

TICKETS = ["t4", "t15", "t16", "t17", "t25", "t26"]


def _w(ws, rel, content):
    p = os.path.join(ws, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)


# ---------------- store/kv.go ----------------

_KV_HEAD = '''package store

// KV is the storage contract used by all services.
type KV interface {
	Get(key string) ([]byte, bool)
	Put(key string, value []byte)
'''

_KV_T4 = '\tPutTTL(key string, value []byte, expiresAt int64) // t4\n'

_KV_TAIL = '''\tDelete(key string)
	Keys(prefix string) []string
}
'''


def _kv_go(on):
    parts = [_KV_HEAD]
    if "t4" in on:
        parts.append(_KV_T4)
    parts.append(_KV_TAIL)
    return "".join(parts)


# ---------------- store/memstore.go ----------------

_MS_ENTRY = '''
type entry struct {
	val []byte
	exp int64 // 0 = never expires
}
'''

# %s: the value type held by Mem.data ("entry" with t4, "[]byte" without).
_MS_MEM = '''
// Mem is an in-memory KV implementation safe for concurrent use.
type Mem struct {
	mu   sync.RWMutex
	data map[string]%s
}

func NewMem() *Mem { return &Mem{data: map[string]%s{}} }
'''

_MS_CP = '''
func cp(b []byte) []byte {
	out := make([]byte, len(b))
	copy(out, b)
	return out
}
'''

_MS_VISIBLE = '''
func (e entry) visible() bool { return e.exp == 0 || util.Now() < e.exp }
'''

# Get variants: (t4, t26) -> body.
_MS_GET = {
    (False, False): '''
func (m *Mem) Get(key string) ([]byte, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	v, ok := m.data[key]
	return v, ok
}
''',
    (False, True): '''
func (m *Mem) Get(key string) ([]byte, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	v, ok := m.data[key]
	if !ok {
		return nil, false
	}
	return cp(v), true // t26: copy out
}
''',
    (True, False): '''
func (m *Mem) Get(key string) ([]byte, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	e, ok := m.data[key]
	if !ok || !e.visible() {
		return nil, false
	}
	return e.val, true
}
''',
    (True, True): '''
func (m *Mem) Get(key string) ([]byte, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	e, ok := m.data[key]
	if !ok || !e.visible() {
		return nil, false
	}
	return cp(e.val), true // t26: copy out
}
''',
}

# %s: the stored value expression.
_MS_PUT = '''
func (m *Mem) Put(key string, value []byte) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data[key] = %s
}
'''

# %s: "cp(value)" with t26, "value" without.
_MS_PUTTTL = '''
// PutTTL (t4): entry invisible once util.Now() >= expiresAt.
func (m *Mem) PutTTL(key string, value []byte, expiresAt int64) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data[key] = entry{val: %s, exp: expiresAt}
}
'''

_MS_DELETE = '''
func (m *Mem) Delete(key string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.data, key)
}
'''

_MS_KEYS_T4 = '''
func (m *Mem) Keys(prefix string) []string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	var out []string
	for k, e := range m.data {
		if strings.HasPrefix(k, prefix) && e.visible() {
			out = append(out, k)
		}
	}
	sort.Strings(out)
	return out
}
'''

_MS_KEYS_BASE = '''
func (m *Mem) Keys(prefix string) []string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	var out []string
	for k := range m.data {
		if strings.HasPrefix(k, prefix) {
			out = append(out, k)
		}
	}
	sort.Strings(out)
	return out
}
'''

_MS_LEN_T4 = '''
// Len (t15): number of visible entries.
func (m *Mem) Len() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	n := 0
	for _, e := range m.data {
		if e.visible() {
			n++
		}
	}
	return n
}
'''

_MS_LEN_BASE = '''
// Len (t15): number of entries.
func (m *Mem) Len() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.data)
}
'''

# %s: the value type held by Mem.data.
_MS_CLEAR = '''
// Clear (t16).
func (m *Mem) Clear() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data = map[string]%s{}
}
'''

_MS_SNAPRESTORE_T4 = '''
// Snapshot (t17): deep copy of current visible entries.
func (m *Mem) Snapshot() map[string][]byte {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := map[string][]byte{}
	for k, e := range m.data {
		if e.visible() {
			out[k] = cp(e.val)
		}
	}
	return out
}

// Restore (t17): replace all entries with a deep copy of s.
func (m *Mem) Restore(s map[string][]byte) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data = map[string]entry{}
	for k, v := range s {
		m.data[k] = entry{val: cp(v)}
	}
}
'''

_MS_SNAPRESTORE_BASE = '''
// Snapshot (t17): deep copy of current entries.
func (m *Mem) Snapshot() map[string][]byte {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := map[string][]byte{}
	for k, v := range m.data {
		out[k] = cp(v)
	}
	return out
}

// Restore (t17): replace all entries with a deep copy of s.
func (m *Mem) Restore(s map[string][]byte) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data = map[string][]byte{}
	for k, v := range s {
		m.data[k] = cp(v)
	}
}
'''

_MS_RANGE_T4 = '''
// Range (t25): visible entries with prefix, ascending, early stop on false.
func (m *Mem) Range(prefix string, fn func(key string, value []byte) bool) {
	m.mu.RLock()
	keys := []string{}
	for k, e := range m.data {
		if strings.HasPrefix(k, prefix) && e.visible() {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)
	vals := map[string][]byte{}
	for _, k := range keys {
		vals[k] = cp(m.data[k].val)
	}
	m.mu.RUnlock()
	for _, k := range keys {
		if !fn(k, vals[k]) {
			return
		}
	}
}
'''

_MS_RANGE_BASE = '''
// Range (t25): entries with prefix, ascending, early stop on false.
func (m *Mem) Range(prefix string, fn func(key string, value []byte) bool) {
	m.mu.RLock()
	keys := []string{}
	for k := range m.data {
		if strings.HasPrefix(k, prefix) {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)
	vals := map[string][]byte{}
	for _, k := range keys {
		vals[k] = cp(m.data[k])
	}
	m.mu.RUnlock()
	for _, k := range keys {
		if !fn(k, vals[k]) {
			return
		}
	}
}
'''


def _memstore_go(on):
    t4 = "t4" in on
    t26 = "t26" in on
    need_cp = t26 or "t17" in on or "t25" in on
    ty = "entry" if t4 else "[]byte"

    parts = ['package store\n\nimport (\n\t"sort"\n\t"strings"\n\t"sync"\n']
    if t4:
        parts.append('\n\t"bench/fleetsvc/util"\n')
    parts.append(")\n")
    if t4:
        parts.append(_MS_ENTRY)
    parts.append(_MS_MEM % (ty, ty))
    if need_cp:
        parts.append(_MS_CP)
    if t4:
        parts.append(_MS_VISIBLE)
    parts.append(_MS_GET[(t4, t26)])
    if t4:
        stored = "entry{val: cp(value)} // t26: copy in" if t26 else "entry{val: value}"
    else:
        stored = "cp(value) // t26: copy in" if t26 else "value"
    parts.append(_MS_PUT % stored)
    if t4:
        parts.append(_MS_PUTTTL % ("cp(value)" if t26 else "value"))
    parts.append(_MS_DELETE)
    parts.append(_MS_KEYS_T4 if t4 else _MS_KEYS_BASE)
    if "t15" in on:
        parts.append(_MS_LEN_T4 if t4 else _MS_LEN_BASE)
    if "t16" in on:
        parts.append(_MS_CLEAR % ty)
    if "t17" in on:
        parts.append(_MS_SNAPRESTORE_T4 if t4 else _MS_SNAPRESTORE_BASE)
    if "t25" in on:
        parts.append(_MS_RANGE_T4 if t4 else _MS_RANGE_BASE)
    return "".join(parts)


def emit(ws, enabled):
    on = set(enabled)
    unknown = on - set(TICKETS)
    if unknown:
        raise ValueError("unknown store tickets: %s" % sorted(unknown))
    _w(ws, "store/kv.go", _kv_go(on))
    _w(ws, "store/memstore.go", _memstore_go(on))
