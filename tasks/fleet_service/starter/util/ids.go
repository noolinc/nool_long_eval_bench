package util

import "fmt"

var counter int

// NewID returns a fresh identifier of the form "<kind>-<n>".
func NewID(kind string) string {
	counter++
	return fmt.Sprintf("%s-%d", kind, counter)
}

// ResetIDs restores the counter; test helper.
func ResetIDs() { counter = 0 }
