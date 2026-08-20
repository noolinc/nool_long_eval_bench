// Reference solution — proves the hidden tests are satisfiable from spec.md
// alone. Never provided to agents; used only by task validation.
package redux

type Action struct {
	Type    string
	Payload any
}

type Dispatcher func(action Action) Action

type Store[S any] struct {
	state     S
	reducer   func(S, Action) S
	listeners map[int]func()
	nextID    int
	dispatch  Dispatcher
}

func CreateStore[S any](reducer func(S, Action) S, initial S) *Store[S] {
	s := &Store[S]{state: initial, reducer: reducer, listeners: map[int]func(){}}
	s.dispatch = s.baseDispatch
	return s
}

func (s *Store[S]) baseDispatch(action Action) Action {
	s.state = s.reducer(s.state, action)
	for _, l := range s.listeners {
		l()
	}
	return action
}

func (s *Store[S]) GetState() S { return s.state }

func (s *Store[S]) Dispatch(action Action) Action { return s.dispatch(action) }

func (s *Store[S]) Subscribe(listener func()) func() {
	id := s.nextID
	s.nextID++
	s.listeners[id] = listener
	return func() { delete(s.listeners, id) }
}

func CombineReducers(reducers map[string]func(any, Action) any) func(map[string]any, Action) map[string]any {
	return func(state map[string]any, action Action) map[string]any {
		next := make(map[string]any, len(state))
		for k, v := range state {
			next[k] = v
		}
		for k, r := range reducers {
			next[k] = r(state[k], action)
		}
		return next
	}
}

type StoreMiddlewareAPI[S any] interface {
	GetState() S
	Dispatch(action Action) Action
}

type Enhancer[S any] func(*Store[S])

func ApplyMiddleware[S any](mws ...func(StoreMiddlewareAPI[S]) func(Dispatcher) Dispatcher) Enhancer[S] {
	return func(s *Store[S]) {
		d := s.baseDispatch
		for i := len(mws) - 1; i >= 0; i-- {
			d = mws[i](s)(d)
		}
		s.dispatch = d
	}
}

func CreateStoreWithEnhancer[S any](reducer func(S, Action) S, initial S, enhancer Enhancer[S]) *Store[S] {
	s := CreateStore(reducer, initial)
	enhancer(s)
	return s
}
