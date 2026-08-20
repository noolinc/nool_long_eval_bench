pub struct Server {
    is_running: bool,
}

impl Server {
    pub fn new() -> Self {
        Server { is_running: false }
    }
<<<<<<< HEAD
    pub fn start(&mut self) {
        self.is_running = true;
=======
    pub fn stop(&mut self) {
        self.is_running = false;
>>>>>>> agent_b
    }
    // Agents will insert methods here
}
