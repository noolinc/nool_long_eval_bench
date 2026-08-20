use std::cell::RefCell;
use std::rc::Rc;

thread_local! {
    static ACTIVE_EFFECT: RefCell<Option<Rc<RefCell<dyn FnMut()>>>> = RefCell::new(None);
}

pub struct Reactive<T> {
    inner: Rc<RefCell<ReactiveInner<T>>>,
}

struct ReactiveInner<T> {
    value: T,
    subscribers: Vec<Rc<RefCell<dyn FnMut()>>>,
}

impl<T> Clone for Reactive<T> {
    fn clone(&self) -> Self {
        Reactive { inner: Rc::clone(&self.inner) }
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
        ACTIVE_EFFECT.with(|active| {
            if let Some(effect) = &*active.borrow() {
                let mut inner = self.inner.borrow_mut();
                let exists = inner.subscribers.iter().any(|sub| Rc::ptr_eq(sub, effect));
                if !exists {
                    inner.subscribers.push(Rc::clone(effect));
                }
            }
        });
        
        self.inner.borrow().value.clone()
    }

    pub fn set(&self, value: T) {
        self.inner.borrow_mut().value = value;
        let subscribers = self.inner.borrow().subscribers.clone();
        for effect in subscribers {
            let mut f = effect.borrow_mut();
            (&mut *f)();
        }
    }
}

pub fn effect(f: Box<dyn FnMut()>) {
    let rc_f: Rc<RefCell<dyn FnMut()>> = Rc::new(RefCell::new(f));
    
    ACTIVE_EFFECT.with(|active| {
        *active.borrow_mut() = Some(Rc::clone(&rc_f));
    });
    
    {
        let mut f_ref = rc_f.borrow_mut();
        (&mut *f_ref)();
    }
    
    ACTIVE_EFFECT.with(|active| {
        *active.borrow_mut() = None;
    });
}
