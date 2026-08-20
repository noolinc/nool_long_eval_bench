package main

type UserService struct {
	name string
}

func (u *UserService) GetName() string {
	return u.name
}

<<<<<<< HEAD
func (u *UserService) SetEmail(email string) {
	// Agent A adds SetEmail method
=======
func (u *UserService) SetAge(age int) {
	// Agent B adds SetAge method
>>>>>>> agent-b
}
