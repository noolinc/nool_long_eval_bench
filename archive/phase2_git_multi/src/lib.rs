use std::rc::{Rc, Weak};
use std::cell::RefCell;

pub struct Effect {
    cb: Box<dyn Fn()>,
    clear_deps: RefCell<Vec<Box<dyn Fn()>>>,
}

impl Effect {
    pub fn new(cb: Box<dyn Fn()>) -> Rc<Self> {
        Rc::new(Effect {
            cb,
            clear_deps: RefCell::new(Vec::new()),
        })
    }

    pub fn run(self: &Rc<Self>) {
        {
            let mut clear_deps = self.clear_deps.borrow_mut();
            for clear in clear_deps.drain(..) {
                clear();
            }
        }

        ACTIVE_EFFECT.with(|active| {
            active.borrow_mut().push(self.clone());
        });
        
        (self.cb)();
        
        ACTIVE_EFFECT.with(|active| {
            active.borrow_mut().pop();
        });
    }
}

thread_local! {
    static ACTIVE_EFFECT: RefCell<Vec<Rc<Effect>>> = RefCell::new(Vec::new());
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

impl<T: Clone + 'static> Reactive<T> {
    pub fn new(value: T) -> Self {
        Reactive {
            inner: Rc::new(RefCell::new(ReactiveInner {
                value,
                subscribers: Vec::new(),
            })),
        }
    }

    pub fn get(&self) -> T {
        ACTIVE_EFFECT.with(|active| {
            if let Some(effect) = active.borrow().last() {
                let mut inner = self.inner.borrow_mut();
                
                let exists = inner.subscribers.iter().any(|weak_sub| {
                    if let Some(sub) = weak_sub.upgrade() {
                        Rc::ptr_eq(&sub, effect)
                    } else {
                        false
                    }
                });
                
                if !exists {
                    let weak_effect = Rc::downgrade(effect);
                    inner.subscribers.push(weak_effect.clone());
                    
                    let inner_weak = Rc::downgrade(&self.inner);
                    effect.clear_deps.borrow_mut().push(Box::new(move || {
                        if let Some(inner) = inner_weak.upgrade() {
                            inner.borrow_mut().subscribers.retain(|sub| {
                                if let Some(s) = sub.upgrade() {
                                    if let Some(e) = weak_effect.upgrade() {
                                        !Rc::ptr_eq(&s, &e)
                                    } else {
                                        false
                                    }
                                } else {
                                    false
                                }
                            });
                        }
                    }));
                }
            }
        });
        self.inner.borrow().value.clone()
    }

    pub fn set(&self, value: T) {
        let mut effects_to_run = Vec::new();
        {
            let mut inner = self.inner.borrow_mut();
            inner.value = value;
            
            inner.subscribers.retain(|weak_sub| {
                if let Some(sub) = weak_sub.upgrade() {
                    effects_to_run.push(sub);
                    true
                } else {
                    false
                }
            });
        }
        
        for effect in effects_to_run {
            effect.run();
        }
    }
}

pub fn effect(cb: Box<dyn Fn()>) -> Rc<Effect> {
    let effect_rc = Effect::new(cb);
    effect_rc.run();
    effect_rc
}
