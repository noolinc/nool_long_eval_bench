package redux

// Hidden acceptance tests. Never shown to agents; copied into the workspace
// only at scoring time. Every call here uses only API shapes stated in
// spec.md — the task must be satisfiable without seeing this file.

import "testing"

type CounterState struct{ Count int }

func counterReducer(state CounterState, action Action) CounterState {
	switch action.Type {
	case "INCREMENT":
		return CounterState{Count: state.Count + 1}
	case "DECREMENT":
		return CounterState{Count: state.Count - 1}
	case "ADD":
		if v, ok := action.Payload.(int); ok {
			return CounterState{Count: state.Count + v}
		}
		return state
	default:
		return state
	}
}

func TestCreateStoreAndDispatch(t *testing.T) {
	store := CreateStore(counterReducer, CounterState{Count: 0})
	if store.GetState().Count != 0 {
		t.Fatalf("initial count = %d, want 0", store.GetState().Count)
	}
	store.Dispatch(Action{Type: "INCREMENT"})
	store.Dispatch(Action{Type: "ADD", Payload: 5})
	store.Dispatch(Action{Type: "DECREMENT"})
	if got := store.GetState().Count; got != 5 {
		t.Errorf("count = %d, want 5", got)
	}
}

func TestSubscribeAndUnsubscribe(t *testing.T) {
	store := CreateStore(counterReducer, CounterState{})
	calls := 0
	unsub := store.Subscribe(func() { calls++ })
	store.Dispatch(Action{Type: "INCREMENT"})
	store.Dispatch(Action{Type: "INCREMENT"})
	if calls != 2 {
		t.Errorf("listener calls = %d, want 2", calls)
	}
	unsub()
	store.Dispatch(Action{Type: "INCREMENT"})
	if calls != 2 {
		t.Errorf("listener calls after unsubscribe = %d, want 2", calls)
	}
}

func TestCombineReducers(t *testing.T) {
	counter := func(state any, action Action) any {
		n, _ := state.(int)
		if action.Type == "INCREMENT" {
			return n + 1
		}
		return n
	}
	todos := func(state any, action Action) any {
		list, _ := state.([]string)
		if action.Type == "ADD_TODO" {
			return append(list, action.Payload.(string))
		}
		return list
	}
	root := CombineReducers(map[string]func(any, Action) any{
		"counter": counter,
		"todos":   todos,
	})
	state := map[string]any{"counter": 0, "todos": []string{}, "untouched": "x"}
	state = root(state, Action{Type: "INCREMENT"})
	state = root(state, Action{Type: "ADD_TODO", Payload: "learn go"})
	if state["counter"].(int) != 1 {
		t.Errorf("counter = %v, want 1", state["counter"])
	}
	if l := state["todos"].([]string); len(l) != 1 || l[0] != "learn go" {
		t.Errorf("todos = %v, want [learn go]", l)
	}
	if state["untouched"] != "x" {
		t.Errorf("untouched key modified: %v", state["untouched"])
	}
}

func TestApplyMiddleware(t *testing.T) {
	var logged []string
	logger := func(api StoreMiddlewareAPI[CounterState]) func(Dispatcher) Dispatcher {
		return func(next Dispatcher) Dispatcher {
			return func(action Action) Action {
				logged = append(logged, action.Type)
				return next(action)
			}
		}
	}
	doubler := func(api StoreMiddlewareAPI[CounterState]) func(Dispatcher) Dispatcher {
		return func(next Dispatcher) Dispatcher {
			return func(action Action) Action {
				if action.Type == "ADD" {
					action.Payload = action.Payload.(int) * 2
				}
				return next(action)
			}
		}
	}
	store := CreateStoreWithEnhancer(counterReducer, CounterState{},
		ApplyMiddleware(logger, doubler))
	store.Dispatch(Action{Type: "INCREMENT"})
	store.Dispatch(Action{Type: "ADD", Payload: 5})
	if got := store.GetState().Count; got != 11 { // 1 + 5*2
		t.Errorf("count = %d, want 11", got)
	}
	if len(logged) != 2 || logged[0] != "INCREMENT" || logged[1] != "ADD" {
		t.Errorf("logged = %v, want [INCREMENT ADD]", logged)
	}
}
