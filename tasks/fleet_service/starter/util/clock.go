package util

// Now returns the current logical time. Tests may override via SetNow.
var nowFn = func() int64 { return 1000 }

func Now() int64 { return nowFn() }

func SetNow(f func() int64) { nowFn = f }
