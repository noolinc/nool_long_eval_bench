package api

import (
	"encoding/json"
	"net/http"
)

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func (a *App) handleUserCreate(w http.ResponseWriter, r *http.Request) {
	email := r.URL.Query().Get("email")
	u, err := a.Users.Create(email)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, u)
}

func (a *App) handleUserGet(w http.ResponseWriter, r *http.Request) {
	u, err := a.Users.Get(r.URL.Query().Get("id"))
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, u)
}

func (a *App) handleUserCount(w http.ResponseWriter, r *http.Request) {
	keys := a.Users.S.Keys("user/")
	writeJSON(w, http.StatusOK, map[string]int{"count": len(keys)})
}

func (a *App) handleOrderCreate(w http.ResponseWriter, r *http.Request) {
	ord, err := a.Orders.Create(r.URL.Query().Get("user_id"), atoi(r.URL.Query().Get("cents")))
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, ord)
}

func atoi(s string) int {
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return n
		}
		n = n*10 + int(c-'0')
	}
	return n
}
