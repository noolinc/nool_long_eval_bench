package redux

import (
	"reflect"
	"sync"
)

// Action represents a Redux action.
type Action struct {
	Type    string
	Payload any
}

// StoreMiddlewareAPI represents the API exposed to middlewares.
type StoreMiddlewareAPI[S any] interface {
	GetState() S
	Dispatch(Action) Action
}

// Dispatcher is a function that dispatches an action.
type Dispatcher func(Action) Action

// Middleware is a function that takes a store API and returns a function that wraps the next dispatcher.
type Middleware[S any] func(StoreMiddlewareAPI[S]) func(Dispatcher) Dispatcher

// Enhancer is a function that wraps CreateStore.
type Enhancer[S any] func(reducer func(S, Action) S, initialState S) Store[S]

// Store represents a Redux store.
type Store[S any] interface {
	StoreMiddlewareAPI[S]
	Subscribe(func()) func()
}

type store[S any] struct {
	state       S
	reducer     func(S, Action) S
	subscribers map[int]func()
	nextSubID   int
	mu          sync.RWMutex
}

func (s *store[S]) GetState() S {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.state
}

func (s *store[S]) Dispatch(action Action) Action {
	s.mu.Lock()
	s.state = s.reducer(s.state, action)
	
	// Create a copy of subscribers to avoid deadlocks or panics if subscribers unsubscribe during dispatch
	var subs []func()
	for _, sub := range s.subscribers {
		subs = append(subs, sub)
	}
	s.mu.Unlock()

	for _, sub := range subs {
		sub()
	}

	return action
}

func (s *store[S]) Subscribe(listener func()) func() {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	if s.subscribers == nil {
		s.subscribers = make(map[int]func())
	}
	
	id := s.nextSubID
	s.nextSubID++
	s.subscribers[id] = listener

	return func() {
		s.mu.Lock()
		defer s.mu.Unlock()
		delete(s.subscribers, id)
	}
}

// CreateStore creates a new Redux store.
func CreateStore[S any](reducer func(S, Action) S, initialState S) Store[S] {
	return &store[S]{
		state:       initialState,
		reducer:     reducer,
		subscribers: make(map[int]func()),
	}
}

// ApplyMiddleware creates an enhancer that applies the given middlewares.
func ApplyMiddleware[S any](middlewares ...Middleware[S]) Enhancer[S] {
	return func(reducer func(S, Action) S, initialState S) Store[S] {
		store := CreateStore(reducer, initialState)
		
		var dispatch Dispatcher
		api := &apiWrapper[S]{
			store: store,
			// According to Redux, middleware's dispatch should call the fully composed dispatch chain
			dispatchFn: func(a Action) Action {
				return dispatch(a)
			},
		}
		
		dispatch = store.Dispatch
		for i := len(middlewares) - 1; i >= 0; i-- {
			dispatch = middlewares[i](api)(dispatch)
		}
		
		return &enhancedStore[S]{
			Store:    store,
			dispatch: dispatch,
		}
	}
}

type apiWrapper[S any] struct {
	store      Store[S]
	dispatchFn Dispatcher
}

func (a *apiWrapper[S]) GetState() S {
	return a.store.GetState()
}

func (a *apiWrapper[S]) Dispatch(action Action) Action {
	return a.dispatchFn(action)
}

type enhancedStore[S any] struct {
	Store[S]
	dispatch Dispatcher
}

func (s *enhancedStore[S]) Dispatch(action Action) Action {
	return s.dispatch(action)
}

// CreateStoreWithEnhancer creates a store with an enhancer.
func CreateStoreWithEnhancer[S any](reducer func(S, Action) S, initialState S, enhancer Enhancer[S]) Store[S] {
	return enhancer(reducer, initialState)
}

// CombineReducers combines multiple reducers into one.
func CombineReducers(reducers map[string]any) any {
	return func(state AppState, action Action) AppState {
		vState := reflect.ValueOf(&state).Elem()
		for key, reducer := range reducers {
			field := vState.FieldByName(key)
			if field.IsValid() {
				reducerVal := reflect.ValueOf(reducer)
				res := reducerVal.Call([]reflect.Value{
					field,
					reflect.ValueOf(action),
				})
				field.Set(res[0])
			}
		}
		return state
	}
}
