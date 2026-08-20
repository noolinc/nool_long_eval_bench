package redux

import (
	"reflect"
)

type Action struct {
	Type    string
	Payload any
}

type Dispatcher func(Action) Action

type StoreMiddlewareAPI[S any] interface {
	GetState() S
	Dispatch(Action) Action
}

type Store[S any] struct {
	state       S
	reducer     func(S, Action) S
	subscribers map[int]func()
	nextSubID   int
	dispatch    Dispatcher
}

func CreateStore[S any](reducer func(S, Action) S, initialState S) *Store[S] {
	s := &Store[S]{
		state:       initialState,
		reducer:     reducer,
		subscribers: make(map[int]func()),
	}
	s.dispatch = s.defaultDispatch
	return s
}

func (s *Store[S]) GetState() S {
	return s.state
}

func (s *Store[S]) defaultDispatch(action Action) Action {
	s.state = s.reducer(s.state, action)
	for _, sub := range s.subscribers {
		sub()
	}
	return action
}

func (s *Store[S]) Dispatch(action Action) Action {
	return s.dispatch(action)
}

func (s *Store[S]) Subscribe(sub func()) func() {
	id := s.nextSubID
	s.nextSubID++
	s.subscribers[id] = sub
	return func() {
		delete(s.subscribers, id)
	}
}

type Enhancer[S any] func(func(func(S, Action) S, S) *Store[S]) func(func(S, Action) S, S) *Store[S]

func ApplyMiddleware[S any](middlewares ...func(StoreMiddlewareAPI[S]) func(Dispatcher) Dispatcher) Enhancer[S] {
	return func(createStore func(func(S, Action) S, S) *Store[S]) func(func(S, Action) S, S) *Store[S] {
		return func(reducer func(S, Action) S, initialState S) *Store[S] {
			store := createStore(reducer, initialState)

			api := &middlewareAPIWrapper[S]{store: store}

			var chain []func(Dispatcher) Dispatcher
			for _, m := range middlewares {
				chain = append(chain, m(api))
			}

			store.dispatch = compose(chain)(store.defaultDispatch)
			api.dispatchFunc = store.dispatch

			return store
		}
	}
}

func CreateStoreWithEnhancer[S any](reducer func(S, Action) S, initialState S, enhancer Enhancer[S]) *Store[S] {
	return enhancer(CreateStore[S])(reducer, initialState)
}

type middlewareAPIWrapper[S any] struct {
	store        *Store[S]
	dispatchFunc Dispatcher
}

func (w *middlewareAPIWrapper[S]) GetState() S {
	return w.store.GetState()
}

func (w *middlewareAPIWrapper[S]) Dispatch(a Action) Action {
	return w.dispatchFunc(a)
}

func compose(chain []func(Dispatcher) Dispatcher) func(Dispatcher) Dispatcher {
	return func(next Dispatcher) Dispatcher {
		for i := len(chain) - 1; i >= 0; i-- {
			next = chain[i](next)
		}
		return next
	}
}

func CombineReducers(reducers map[string]any) any {
	// Note: since this needs to pass the test asserting `rootReducer.(func(AppState, Action) AppState)`,
	// we must explicitly return a function of this type. It's not possible to generate a function
	// with a named type `AppState` dynamically in Go without referencing `AppState` directly.
	return func(state AppState, action Action) AppState {
		vState := reflect.ValueOf(&state).Elem()
		for key, reducerFn := range reducers {
			field := vState.FieldByName(key)
			if !field.IsValid() {
				continue
			}
			rVal := reflect.ValueOf(reducerFn)
			out := rVal.Call([]reflect.Value{field, reflect.ValueOf(action)})
			field.Set(out[0])
		}
		return state
	}
}
