package main

import "testing"

func TestServer(t *testing.T) {
	s := NewServer("localhost", 8080)
	if s.host != "localhost" || s.port != 8080 {
		t.Fatal("Failed")
	}
}
