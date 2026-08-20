package redux

import (
	"reflect"
	"testing"
)

// Define basic state for testing
type CounterState struct {
	Count int
}

func counterReducer(state CounterState, action Action) CounterState {
	switch action.Type {
	case "INCREMENT":
		return CounterState{Count: state.Count + 1}
	case "DECREMENT":
		return CounterState{Count: state.Count - 1}
	case "ADD":
		val, ok := action.Payload.(int)
		if ok {
			return CounterState{Count: state.Count + val}
		}
		return state
	default:
		return state
	}
}

func TestCreateStore(t *testing.T) {
	initialState := CounterState{Count: 0}
	store := CreateStore(counterReducer, initialState)

	if store.GetState().Count != 0 {
		t.Errorf("Expected initial state count to be 0, got %d", store.GetState().Count)
	}
}

func TestDispatchAndSubscribe(t *testing.T) {
	initialState := CounterState{Count: 0}
	store := CreateStore(counterReducer, initialState)

	notified := false
	unsubscribe := store.Subscribe(func() {
		notified = true
	})

	store.Dispatch(Action{Type: "INCREMENT"})

	if !notified {
		t.Errorf("Expected subscriber to be notified")
	}

	if store.GetState().Count != 1 {
		t.Errorf("Expected state count to be 1, got %d", store.GetState().Count)
	}

	unsubscribe()
	notified = false
	store.Dispatch(Action{Type: "INCREMENT"})

	if notified {
		t.Errorf("Expected subscriber NOT to be notified after unsubscribe")
	}
}

// Test for CombineReducers
type AppState struct {
	Counter CounterState
	Todos   []string
}

func todoReducer(state []string, action Action) []string {
	if state == nil {
		state = []string{}
	}
	switch action.Type {
	case "ADD_TODO":
		return append(state, action.Payload.(string))
	default:
		return state
	}
}

func TestCombineReducers(t *testing.T) {
	rootReducer := CombineReducers(map[string]any{
		"Counter": counterReducer,
		"Todos":   todoReducer,
	})

	// Use type assertion for the returned generic reducer
	reducer, ok := rootReducer.(func(AppState, Action) AppState)
	if !ok {
		t.Fatalf("CombineReducers did not return a valid reducer func(AppState, Action) AppState")
	}

	initialState := AppState{
		Counter: CounterState{Count: 0},
		Todos:   []string{},
	}

	store := CreateStore(reducer, initialState)

	store.Dispatch(Action{Type: "INCREMENT"})
	store.Dispatch(Action{Type: "ADD_TODO", Payload: "Learn Go"})

	state := store.GetState()
	if state.Counter.Count != 1 {
		t.Errorf("Expected counter to be 1, got %d", state.Counter.Count)
	}
	if len(state.Todos) != 1 || state.Todos[0] != "Learn Go" {
		t.Errorf("Expected todos to contain 'Learn Go', got %v", state.Todos)
	}
}

func TestApplyMiddleware(t *testing.T) {
	var loggedActions []string

	// Middleware that logs action types
	loggerMiddleware := func(store StoreMiddlewareAPI[CounterState]) func(Dispatcher) Dispatcher {
		return func(next Dispatcher) Dispatcher {
			return func(action Action) Action {
				loggedActions = append(loggedActions, action.Type)
				return next(action)
			}
		}
	}

	// Middleware that intercepts and modifies payload
	modifierMiddleware := func(store StoreMiddlewareAPI[CounterState]) func(Dispatcher) Dispatcher {
		return func(next Dispatcher) Dispatcher {
			return func(action Action) Action {
				if action.Type == "ADD" {
					action.Payload = action.Payload.(int) * 2 // Double the addition
				}
				return next(action)
			}
		}
	}

	initialState := CounterState{Count: 0}
	enhancer := ApplyMiddleware(loggerMiddleware, modifierMiddleware)
	store := CreateStoreWithEnhancer(counterReducer, initialState, enhancer)

	store.Dispatch(Action{Type: "INCREMENT"})
	store.Dispatch(Action{Type: "ADD", Payload: 5})

	if store.GetState().Count != 11 { // 0 + 1 + (5 * 2) = 11
		t.Errorf("Expected state count to be 11, got %d", store.GetState().Count)
	}

	if len(loggedActions) != 2 || loggedActions[0] != "INCREMENT" || loggedActions[1] != "ADD" {
		t.Errorf("Expected logger to log [INCREMENT, ADD], got %v", loggedActions)
	}
}
