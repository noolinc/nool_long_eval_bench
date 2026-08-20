use std::cell::RefCell;
use std::rc::Rc;

type EffectFn = Rc<RefCell<Box<dyn FnMut()>>>;

thread_local! {
    static ACTIVE_EFFECT: RefCell<Option<EffectFn>> = RefCell::new(None);
}

pub struct Reactive<T> {
    value: Rc<RefCell<T>>,
    subscribers: Rc<RefCell<Vec<EffectFn>>>,
}

impl<T> Clone for Reactive<T> {
    fn clone(&self) -> Self {
        Reactive {
            value: self.value.clone(),
            subscribers: self.subscribers.clone(),
        }
    }
}

impl<T: Clone> Reactive<T> {
    pub fn new(value: T) -> Self {
        Reactive {
            value: Rc::new(RefCell::new(value)),
            subscribers: Rc::new(RefCell::new(Vec::new())),
        }
    }

    pub fn get(&self) -> T {
        ACTIVE_EFFECT.with(|active| {
            if let Some(effect) = active.borrow().as_ref() {
                let mut subs = self.subscribers.borrow_mut();
                let mut found = false;
                for sub in subs.iter() {
                    if Rc::ptr_eq(sub, effect) {
                        found = true;
                        break;
                    }
                }
                if !found {
                    subs.push(effect.clone());
                }
            }
        });
        self.value.borrow().clone()
    }

    pub fn set(&self, new_value: T) {
        *self.value.borrow_mut() = new_value;
        let subs = self.subscribers.borrow().clone();
        for sub in subs {
            ACTIVE_EFFECT.with(|active| {
                *active.borrow_mut() = Some(sub.clone());
            });
            {
                let mut func = sub.borrow_mut();
                func();
            }
            ACTIVE_EFFECT.with(|active| {
                *active.borrow_mut() = None;
            });
        }
    }
}

pub fn effect(f: Box<dyn FnMut()>) {
    let shared_effect: EffectFn = Rc::new(RefCell::new(f));
    
    ACTIVE_EFFECT.with(|active| {
        *active.borrow_mut() = Some(shared_effect.clone());
    });
    
    {
        let mut func = shared_effect.borrow_mut();
        func();
    }
    
    ACTIVE_EFFECT.with(|active| {
        *active.borrow_mut() = None;
    });
}
