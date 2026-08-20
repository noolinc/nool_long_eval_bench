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
	fmt.Printf("Server on %s:%d\n", s.host, s.port)
}

func (s *Server) Restart() {
	fmt.Println("Server restarted")
}
