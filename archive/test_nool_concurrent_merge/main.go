package main

import "fmt"

type UserService struct {
	name string
}

func (u *UserService) GetName() string {
	return u.name
}

<<<<<<< HEAD
func (u *UserService) SetEmail(email string) {
	fmt.Println("Set email:", email)
=======
func (u *UserService) SetAge(age int) {
	fmt.Println("Set age:", age)
>>>>>>> agent-b
}

func main() {
	u := &UserService{name: "Alice"}
	fmt.Println(u.GetName())
}
