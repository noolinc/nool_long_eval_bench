package api

import "fmt"

func HandleRequest(path string) string {
	return fmt.Sprintf("Response for %s", path)
}
