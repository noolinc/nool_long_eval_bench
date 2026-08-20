package redux

import (
	"reflect"
	"sync"
)

// Action represents an action that can be dispatched to the store.
type Action struct {
	Type    string
	Payload any
}

// Reducer is a function that takes a state and an action and returns a new state.
type Reducer[T any] func(state T, action Action) T

// Store is the core Redux store interface.
type Store[T any] interface {
	GetState() T
	Dispatch(action Action) Action
	Subscribe(listener func()) func()
}

type storeImpl[T any] struct {
	mu        sync.RWMutex
	state     T
	reducer   Reducer[T]
	listeners map[int]func()
	nextID    int
}

func (s *storeImpl[T]) GetState() T {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.state
}

func (s *storeImpl[T]) Dispatch(action Action) Action {
	s.mu.Lock()
	s.state = s.reducer(s.state, action)
	// Collect listeners to call them outside the lock to prevent deadlocks if listeners dispatch actions
	var listeners []func()
	for _, listener := range s.listeners {
		listeners = append(listeners, listener)
	}
	s.mu.Unlock()

	for _, listener := range listeners {
		listener()
	}
	return action
}

func (s *storeImpl[T]) Subscribe(listener func()) func() {
	s.mu.Lock()
	if s.listeners == nil {
		s.listeners = make(map[int]func())
	}
	id := s.nextID
	s.nextID++
	s.listeners[id] = listener
	s.mu.Unlock()

	return func() {
		s.mu.Lock()
		defer s.mu.Unlock()
		delete(s.listeners, id)
	}
}

// CreateStore creates a new Redux store.
func CreateStore[T any](reducer Reducer[T], initialState T) Store[T] {
	return &storeImpl[T]{
		state:     initialState,
		reducer:   reducer,
		listeners: make(map[int]func()),
	}
}

// CombineReducers combines multiple reducers into a single reducer for a generic root state type T.
func CombineReducers[T any](reducers map[string]any) Reducer[T] {
	return func(state T, action Action) T {
		val := reflect.ValueOf(&state).Elem()
		for key, reducer := range reducers {
			field := val.FieldByName(key)
			if field.IsValid() && field.CanSet() {
				reducerVal := reflect.ValueOf(reducer)
				args := []reflect.Value{field, reflect.ValueOf(action)}
				res := reducerVal.Call(args)
				field.Set(res[0])
			}
		}
		return state
	}
}

// Dispatcher is a function that takes an action and returns an action.
type Dispatcher func(Action) Action

// StoreMiddlewareAPI provides the store API to middleware.
type StoreMiddlewareAPI[T any] interface {
	GetState() T
	Dispatch(Action) Action
}

type middlewareAPI[T any] struct {
	store    Store[T]
	dispatch Dispatcher
}

func (m *middlewareAPI[T]) GetState() T {
	return m.store.GetState()
}

func (m *middlewareAPI[T]) Dispatch(action Action) Action {
	return m.dispatch(action)
}

// Middleware is a function that wraps a dispatcher.
type Middleware[T any] func(StoreMiddlewareAPI[T]) func(Dispatcher) Dispatcher

// StoreCreator is a function that creates a store.
type StoreCreator[T any] func(Reducer[T], T) Store[T]

// Enhancer is a function that wraps a store creator.
type Enhancer[T any] func(StoreCreator[T]) StoreCreator[T]

// ApplyMiddleware creates an enhancer that applies the given middlewares.
func ApplyMiddleware[T any](middlewares ...Middleware[T]) Enhancer[T] {
	return func(next StoreCreator[T]) StoreCreator[T] {
		return func(reducer Reducer[T], initialState T) Store[T] {
			store := next(reducer, initialState)
			api := &middlewareAPI[T]{
				store: store,
			}
			
			dispatch := store.Dispatch
			for i := len(middlewares) - 1; i >= 0; i-- {
				dispatch = middlewares[i](api)(dispatch)
			}
			api.dispatch = dispatch

			return &enhancedStore[T]{
				Store:    store,
				dispatch: dispatch,
			}
		}
	}
}

type enhancedStore[T any] struct {
	Store[T]
	dispatch Dispatcher
}

func (e *enhancedStore[T]) Dispatch(action Action) Action {
	return e.dispatch(action)
}

// CreateStoreWithEnhancer creates a new store with the given enhancer.
func CreateStoreWithEnhancer[T any](reducer Reducer[T], initialState T, enhancer Enhancer[T]) Store[T] {
	return enhancer(CreateStore[T])(reducer, initialState)
}
