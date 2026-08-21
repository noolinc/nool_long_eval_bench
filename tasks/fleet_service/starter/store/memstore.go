package store

import (
	"sort"
	"strings"
	"sync"
)

// Mem is an in-memory KV implementation safe for concurrent use.
type Mem struct {
	mu   sync.RWMutex
	data map[string][]byte
}

func NewMem() *Mem { return &Mem{data: map[string][]byte{}} }

func (m *Mem) Get(key string) ([]byte, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	v, ok := m.data[key]
	return v, ok
}

func (m *Mem) Put(key string, value []byte) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data[key] = value
}

func (m *Mem) Delete(key string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.data, key)
}

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

func (m *Mem) Len() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.data)
}

