use vue_reactivity::{Reactive, effect};
use std::rc::Rc;
use std::cell::RefCell;

#[test]
fn test_basic_reactivity() {
    let state = Reactive::new(0);
    
    let dummy = Rc::new(RefCell::new(0));
    let dummy_clone = dummy.clone();
    
    let state_clone = state.clone();
    effect(Box::new(move || {
        *dummy_clone.borrow_mut() = state_clone.get();
    }));
    
    // Effect should run immediately on initialization
    assert_eq!(*dummy.borrow(), 0);
    
    // Changing the state should synchronously trigger the effect
    state.set(1);
    assert_eq!(*dummy.borrow(), 1);
    
    state.set(10);
    assert_eq!(*dummy.borrow(), 10);
}

#[test]
fn test_multiple_effects_on_single_signal() {
    let state = Reactive::new(5);
    
    let sum1 = Rc::new(RefCell::new(0));
    let sum2 = Rc::new(RefCell::new(0));
    
    let s1 = state.clone();
    let d1 = sum1.clone();
    effect(Box::new(move || {
        *d1.borrow_mut() = s1.get() + 1;
    }));
    
    let s2 = state.clone();
    let d2 = sum2.clone();
    effect(Box::new(move || {
        *d2.borrow_mut() = s2.get() + 2;
    }));
    
    assert_eq!(*sum1.borrow(), 6);
    assert_eq!(*sum2.borrow(), 7);
    
    state.set(10);
    
    assert_eq!(*sum1.borrow(), 11);
    assert_eq!(*sum2.borrow(), 12);
}
