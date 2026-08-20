package store

// KV is the storage contract used by all services.
type KV interface {
	Get(key string) ([]byte, bool)
	Put(key string, value []byte)
	Delete(key string)
	Keys(prefix string) []string
}
