package redux

import (
	"reflect"
	"sync"
)

type Action struct {
	Type    string
	Payload any
}

type Dispatcher func(Action) Action

type Store[State any] interface {
	GetState() State
	Dispatch(Action) Action
	Subscribe(func()) func()
}

type StoreMiddlewareAPI[State any] interface {
	GetState() State
	Dispatch(Action) Action
}

type storeImpl[State any] struct {
	mu          sync.RWMutex
	state       State
	reducer     func(State, Action) State
	subscribers map[int]func()
	nextSubId   int
}

func (s *storeImpl[State]) GetState() State {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.state
}

func (s *storeImpl[State]) Dispatch(action Action) Action {
	s.mu.Lock()
	s.state = s.reducer(s.state, action)
	subs := make([]func(), 0, len(s.subscribers))
	for _, sub := range s.subscribers {
		subs = append(subs, sub)
	}
	s.mu.Unlock()

	// Call subscribers outside the lock to avoid deadlocks
	for _, sub := range subs {
		sub()
	}
	return action
}

func (s *storeImpl[State]) Subscribe(listener func()) func() {
	s.mu.Lock()
	defer s.mu.Unlock()

	id := s.nextSubId
	s.nextSubId++
	if s.subscribers == nil {
		s.subscribers = make(map[int]func())
	}
	s.subscribers[id] = listener

	return func() {
		s.mu.Lock()
		defer s.mu.Unlock()
		delete(s.subscribers, id)
	}
}

func CreateStore[State any](reducer func(State, Action) State, initialState State) Store[State] {
	return &storeImpl[State]{
		state:       initialState,
		reducer:     reducer,
		subscribers: make(map[int]func()),
	}
}

type Middleware[State any] func(StoreMiddlewareAPI[State]) func(Dispatcher) Dispatcher

type storeMiddlewareAPIImpl[State any] struct {
	store    Store[State]
	dispatch Dispatcher
}

func (api *storeMiddlewareAPIImpl[State]) GetState() State {
	return api.store.GetState()
}

func (api *storeMiddlewareAPIImpl[State]) Dispatch(action Action) Action {
	return api.dispatch(action)
}

type enhancedStore[State any] struct {
	Store[State]
	dispatch Dispatcher
}

func (s *enhancedStore[State]) Dispatch(action Action) Action {
	return s.dispatch(action)
}

func ApplyMiddleware[State any](middlewares ...Middleware[State]) func(func(func(State, Action) State, State) Store[State]) func(func(State, Action) State, State) Store[State] {
	return func(createStore func(func(State, Action) State, State) Store[State]) func(func(State, Action) State, State) Store[State] {
		return func(reducer func(State, Action) State, initialState State) Store[State] {
			store := createStore(reducer, initialState)
			api := &storeMiddlewareAPIImpl[State]{
				store: store,
			}
			
			// Initialize dispatch to dummy panic function to prevent dispatching during construction
			api.dispatch = func(action Action) Action {
				panic("Dispatching while constructing your middleware is not allowed.")
			}

			dispatch := store.Dispatch
			var chain []func(Dispatcher) Dispatcher
			for _, m := range middlewares {
				chain = append(chain, m(api))
			}
			for i := len(chain) - 1; i >= 0; i-- {
				dispatch = chain[i](dispatch)
			}
			api.dispatch = dispatch
			return &enhancedStore[State]{
				Store:    store,
				dispatch: dispatch,
			}
		}
	}
}

func CreateStoreWithEnhancer[State any](
	reducer func(State, Action) State,
	initialState State,
	enhancer func(func(func(State, Action) State, State) Store[State]) func(func(State, Action) State, State) Store[State],
) Store[State] {
	return enhancer(CreateStore[State])(reducer, initialState)
}

func CombineReducers[T any](reducers map[string]any) func(T, Action) T {
	return func(state T, action Action) T {
		stateVal := reflect.ValueOf(state)
		newState := reflect.New(reflect.TypeOf(state)).Elem()
		newState.Set(stateVal) // Copy original state

		for key, reducerAny := range reducers {
			reducerFn := reflect.ValueOf(reducerAny)
			field := newState.FieldByName(key)
			if !field.IsValid() {
				continue
			}

			currentFieldValue := stateVal.FieldByName(key)
			out := reducerFn.Call([]reflect.Value{currentFieldValue, reflect.ValueOf(action)})
			field.Set(out[0])
		}

		return newState.Interface().(T)
	}
}
