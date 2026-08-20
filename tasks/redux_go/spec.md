# Task: Redux-style state container in Go

Implement a Redux-style state management library in this repository, in
package `redux` (module is already set up in `go.mod`). Put the
implementation in `redux.go`. Do not write tests; acceptance tests already
exist elsewhere and will be run against your code.

Your implementation must provide exactly this API:

```go
// Action carries a type tag and an optional payload.
type Action struct {
    Type    string
    Payload any
}

// Dispatcher consumes an action and returns it (possibly modified).
type Dispatcher func(action Action) Action

// CreateStore builds a store from a reducer func(S, Action) S and an
// initial state S. The returned store must provide:
//   GetState() S
//   Dispatch(action Action) Action
//   Subscribe(listener func()) (unsubscribe func())
// Dispatch applies the reducer and then notifies all subscribed listeners.
// Unsubscribe must stop future notifications for that listener.
func CreateStore[S any](reducer func(S, Action) S, initial S) *Store[S]

// CombineReducers composes per-key reducers over a map-shaped state.
// The returned reducer applies each sub-reducer to its key's current value
// (nil when the key is absent) and stores the result under that key. Keys
// without a registered reducer are passed through unchanged.
func CombineReducers(reducers map[string]func(any, Action) any) func(map[string]any, Action) map[string]any

// Middleware wraps dispatch. StoreMiddlewareAPI[S] exposes GetState and
// Dispatch to middleware. ApplyMiddleware composes middlewares into an
// enhancer; CreateStoreWithEnhancer builds a store whose Dispatch runs the
// middleware chain left-to-right before the reducer.
type StoreMiddlewareAPI[S any] interface { ... }
func ApplyMiddleware[S any](mws ...func(StoreMiddlewareAPI[S]) func(Dispatcher) Dispatcher) Enhancer[S]
func CreateStoreWithEnhancer[S any](reducer func(S, Action) S, initial S, enhancer Enhancer[S]) *Store[S]
```

Exact receiver/type shapes beyond these signatures are your design choice as
long as calls of the forms above compile and behave as described. The code
must build with `go build ./...`.

When your implementation is complete and builds cleanly, land your work with
the version-control workflow available in this repository, then stop.
