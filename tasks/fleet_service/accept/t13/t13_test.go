package t13

import (
	"testing"
	"net/http/httptest"

	"bench/fleetsvc/api"
	"bench/fleetsvc/service"
	"bench/fleetsvc/store"
)

func TestRequestLog(t *testing.T) {
	s := store.NewMem()
	app := &api.App{Users: &service.Users{S: s}, Orders: &service.Orders{S: s}}
	r := app.Router()
	before := len(api.RequestLog())
	r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/users/get?id=x", nil))
	r.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/users/create?email=a@b.co", nil))
	log := api.RequestLog()
	if len(log) != before+2 {
		t.Fatalf("RequestLog grew by %d, want 2", len(log)-before)
	}
	if log[len(log)-2] != "/users/get" || log[len(log)-1] != "/users/create" {
		t.Fatalf("logged paths = %v", log[len(log)-2:])
	}
}
