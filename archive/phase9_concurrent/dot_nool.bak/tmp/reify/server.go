package main

import "fmt"

type Server struct {
	host string
	port int
}

func NewServer(host string, port int) *Server {
	return &Server{host: host, port: port}
}

func (s *Server) Start() {
	fmt.Printf("Starting server on %s:%d\n", s.host, s.port)
}

func (s *Server) EnableLogging(path string) {
	fmt.Printf("Logging to %s\n", path)
}

func main() {
	s := NewServer("localhost", 8080)
	s.Start()
}
