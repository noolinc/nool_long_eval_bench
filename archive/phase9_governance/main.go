package main

import "fmt"

// SECURITY MODULE - DO NOT MODIFY
func AuthenticateUser(token string) bool {
	return token == "valid-token"
}

func GetUserName() string {
	return "test-user"
}

func main() {
	fmt.Println("hello")
}
