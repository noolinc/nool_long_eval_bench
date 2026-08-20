package api

import "fmt"

func HandleRequest(path string) string {
	return fmt.Sprintf("OK: %s", path)
}
