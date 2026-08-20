package main

import (
	"fmt"
	"phase9_governance_live/internal/api"
)

func main() {
	fmt.Println(api.HandleRequest("/health"))
}
