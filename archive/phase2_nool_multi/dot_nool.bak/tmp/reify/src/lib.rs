use std::cell::RefCell;
use std::collections::HashMap;
use std::rc::{Rc, Weak};

thread_local! {
    static ACTIVE_EFFECT_STACK: RefCell<Vec<Weak<Effect>>> = RefCell::new(Vec::new());
    static EFFECTS: RefCell<HashMap<usize, Rc<Effect>>> = RefCell::new(HashMap::new());
    static NEXT_EFFECT_ID: RefCell<usize> = RefCell::new(1);
}

pub struct Effect {
    id: usize,
    f: Box<dyn Fn()>,
}

impl Effect {
    fn run(self: &Rc<Self>) {
        ACTIVE_EFFECT_STACK.with(|stack| {
            stack.borrow_mut().push(Rc::downgrade(self));
        });

        struct StackGuard;
        impl Drop for StackGuard {
            fn drop(&mut self) {
                ACTIVE_EFFECT_STACK.with(|stack| {
                    stack.borrow_mut().pop();
                });
            }
        }
        let _guard = StackGuard;

        (self.f)();
    }
}

pub fn effect(f: Box<dyn Fn()>) -> usize {
    let id = NEXT_EFFECT_ID.with(|n| {
        let mut n = n.borrow_mut();
        let id = *n;
        *n += 1;
        id
    });

    let effect = Rc::new(Effect { id, f });
    
    EFFECTS.with(|effects| {
        effects.borrow_mut().insert(id, effect.clone());
    });

    effect.run();
    
    id
}

pub fn stop(id: usize) {
    EFFECTS.with(|effects| {
        effects.borrow_mut().remove(&id);
    });
}

pub struct Reactive<T> {
    inner: Rc<RefCell<ReactiveInner<T>>>,
}

struct ReactiveInner<T> {
    value: T,
    subscribers: Vec<Weak<Effect>>,
}

impl<T> Clone for Reactive<T> {
    fn clone(&self) -> Self {
        Reactive {
            inner: self.inner.clone(),
        }
    }
}

impl<T: Clone> Reactive<T> {
    pub fn new(value: T) -> Self {
        Reactive {
            inner: Rc::new(RefCell::new(ReactiveInner {
                value,
                subscribers: Vec::new(),
            })),
        }
    }

    pub fn get(&self) -> T {
        ACTIVE_EFFECT_STACK.with(|stack| {
            if let Some(current_effect_weak) = stack.borrow().last() {
                if let Some(current_effect) = current_effect_weak.upgrade() {
                    let mut inner = self.inner.borrow_mut();
                    let exists = inner.subscribers.iter().any(|weak| {
                        if let Some(effect) = weak.upgrade() {
                            effect.id == current_effect.id
                        } else {
                            false
                        }
                    });
                    if !exists {
                        inner.subscribers.push(Rc::downgrade(&current_effect));
                    }
                }
            }
        });
        self.inner.borrow().value.clone()
    }

    pub fn set(&self, value: T) {
        let _old_value;
        let mut active_subscribers = Vec::new();
        {
            let mut inner = self.inner.borrow_mut();
            _old_value = std::mem::replace(&mut inner.value, value);
            
            inner.subscribers.retain(|weak| {
                if let Some(effect) = weak.upgrade() {
                    active_subscribers.push(effect);
                    true
                } else {
                    false
                }
            });
        } // inner borrow is released here, before _old_value is dropped
        
        for effect in active_subscribers {
            effect.run();
        }
    }
}
