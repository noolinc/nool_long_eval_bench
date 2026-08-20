package api

import (
	"net/http"

	"bench/fleetsvc/service"
)

type App struct {
	Users  *service.Users
	Orders *service.Orders
}

// Router wires all HTTP endpoints.
func (a *App) Router() *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/users/create", a.handleUserCreate)
	mux.HandleFunc("/users/get", a.handleUserGet)
	mux.HandleFunc("/orders/create", a.handleOrderCreate)
	return mux
}
