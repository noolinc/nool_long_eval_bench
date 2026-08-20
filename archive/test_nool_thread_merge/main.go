package main

import "fmt"

type UserService struct {
	name string
}

func (u *UserService) GetName() string {
	return u.name
}

func (u *UserService) SetAge(age int) {
	fmt.Println("Set age:", age)
}

func main() {
	u := &UserService{name: "Alice"}
	fmt.Println(u.GetName())
}
