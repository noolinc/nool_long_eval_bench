"""Corpus v3 independent fillers t41-t60: one new file each, pure functions,
edge cases pinned in the spec text and tested exactly as pinned."""

F = {}

F["t41"] = ("String truncation", ["util/truncate.go"],
 "Create util/truncate.go with `func Truncate(s string, n int) string`: the first n runes of s (the whole string when it has n runes or fewer); n <= 0 returns \"\".",
 '''package t41

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestTruncate(t *testing.T) {
	if got := util.Truncate("hello", 3); got != "hel" {
		t.Fatalf("Truncate(hello,3) = %q, want hel", got)
	}
	if got := util.Truncate("hi", 10); got != "hi" {
		t.Fatalf("Truncate(hi,10) = %q, want hi", got)
	}
	if got := util.Truncate("héllo", 2); got != "hé" {
		t.Fatalf("rune truncation = %q, want hé", got)
	}
	if got := util.Truncate("x", 0); got != "" {
		t.Fatalf("Truncate(x,0) = %q, want empty", got)
	}
}
''')

F["t42"] = ("String reversal", ["util/reverse.go"],
 "Create util/reverse.go with `func ReverseString(s string) string` reversing the sequence of runes.",
 '''package t42

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestReverseString(t *testing.T) {
	if got := util.ReverseString("abc"); got != "cba" {
		t.Fatalf("ReverseString(abc) = %q, want cba", got)
	}
	if got := util.ReverseString(util.ReverseString("héllo")); got != "héllo" {
		t.Fatalf("double reverse = %q, want héllo", got)
	}
	if got := util.ReverseString(""); got != "" {
		t.Fatalf("ReverseString(empty) = %q, want empty", got)
	}
}
''')

F["t43"] = ("Integer clamping", ["util/clamp.go"],
 "Create util/clamp.go with `func ClampInt(v, lo, hi int) int`: lo when v < lo, hi when v > hi, otherwise v. When lo > hi, return lo.",
 '''package t43

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestClampInt(t *testing.T) {
	cases := [][4]int{{5, 1, 10, 5}, {-3, 1, 10, 1}, {42, 1, 10, 10}, {7, 9, 2, 9}}
	for _, c := range cases {
		if got := util.ClampInt(c[0], c[1], c[2]); got != c[3] {
			t.Fatalf("ClampInt(%d,%d,%d) = %d, want %d", c[0], c[1], c[2], got, c[3])
		}
	}
}
''')

F["t44"] = ("Absolute value", ["util/abs.go"],
 "Create util/abs.go with `func AbsInt(v int) int` returning the absolute value.",
 '''package t44

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestAbsInt(t *testing.T) {
	for _, c := range [][2]int{{5, 5}, {-5, 5}, {0, 0}} {
		if got := util.AbsInt(c[0]); got != c[1] {
			t.Fatalf("AbsInt(%d) = %d, want %d", c[0], got, c[1])
		}
	}
}
''')

F["t45"] = ("Retry backoff", ["util/backoff.go"],
 "Create util/backoff.go with `func Backoff(attempt int) int64`: 100 * 2^attempt milliseconds, capped at 10000; any attempt <= 0 returns 100.",
 '''package t45

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestBackoff(t *testing.T) {
	cases := []struct {
		attempt int
		want    int64
	}{{-1, 100}, {0, 100}, {1, 200}, {3, 800}, {6, 6400}, {7, 10000}, {30, 10000}}
	for _, c := range cases {
		if got := util.Backoff(c.attempt); got != c.want {
			t.Fatalf("Backoff(%d) = %d, want %d", c.attempt, got, c.want)
		}
	}
}
''')

F["t46"] = ("Slug generation", ["util/slug.go"],
 "Create util/slug.go with `func Slug(s string) string`: lowercase the string; keep ASCII letters and digits; replace every maximal run of any other characters with a single '-'; trim leading and trailing '-'.",
 '''package t46

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestSlug(t *testing.T) {
	cases := [][2]string{
		{"Hello, World!", "hello-world"},
		{"  a  b  ", "a-b"},
		{"Go1.21 rocks", "go1-21-rocks"},
		{"---", ""},
	}
	for _, c := range cases {
		if got := util.Slug(c[0]); got != c[1] {
			t.Fatalf("Slug(%q) = %q, want %q", c[0], got, c[1])
		}
	}
}
''')

F["t47"] = ("Money formatting", ["model/money.go"],
 "Create model/money.go with `func FormatCents(c int) string` rendering cents as dollars: \"12.34\" for 1234, two-digit cents always, negative amounts with a leading '-' (FormatCents(-5) == \"-0.05\").",
 '''package t47

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestFormatCents(t *testing.T) {
	cases := []struct {
		c    int
		want string
	}{{1234, "12.34"}, {5, "0.05"}, {0, "0.00"}, {-5, "-0.05"}, {-1234, "-12.34"}, {100, "1.00"}}
	for _, c := range cases {
		if got := model.FormatCents(c.c); got != c.want {
			t.Fatalf("FormatCents(%d) = %q, want %q", c.c, got, c.want)
		}
	}
}
''')

F["t48"] = ("ZIP validation", ["model/zip.go"],
 "Create model/zip.go with `func ValidZip(s string) bool`: true iff s is exactly five ASCII digits.",
 '''package t48

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestValidZip(t *testing.T) {
	for _, ok := range []string{"12345", "00000"} {
		if !model.ValidZip(ok) {
			t.Fatalf("ValidZip(%q) = false, want true", ok)
		}
	}
	for _, bad := range []string{"1234", "123456", "12a45", "", "12 45"} {
		if model.ValidZip(bad) {
			t.Fatalf("ValidZip(%q) = true, want false", bad)
		}
	}
}
''')

F["t49"] = ("Atomic counter", ["store/counter.go"],
 "Create store/counter.go with a `Counter` type: `func NewCounter() *Counter`, `func (c *Counter) Inc() int` (increment by one and return the new value), `func (c *Counter) Value() int`. Safe for concurrent use.",
 '''package t49

import (
	"sync"
	"testing"

	"bench/fleetsvc/store"
)

func TestCounter(t *testing.T) {
	c := store.NewCounter()
	if got := c.Inc(); got != 1 {
		t.Fatalf("first Inc = %d, want 1", got)
	}
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); c.Inc() }()
	}
	wg.Wait()
	if got := c.Value(); got != 51 {
		t.Fatalf("Value = %d, want 51", got)
	}
}
''')

F["t50"] = ("Prefix counting", ["store/prefixcount.go"],
 "Create store/prefixcount.go with `func CountPrefix(kv KV, prefix string) int` returning the number of visible keys with the prefix (as reported by Keys).",
 '''package t50

import (
	"testing"

	"bench/fleetsvc/store"
)

func TestCountPrefix(t *testing.T) {
	m := store.NewMem()
	m.Put("a/1", []byte("x"))
	m.Put("a/2", []byte("y"))
	m.Put("b/1", []byte("z"))
	if got := store.CountPrefix(m, "a/"); got != 2 {
		t.Fatalf("CountPrefix(a/) = %d, want 2", got)
	}
	if got := store.CountPrefix(m, "c/"); got != 0 {
		t.Fatalf("CountPrefix(c/) = %d, want 0", got)
	}
}
''')

F["t51"] = ("String set", ["util/set.go"],
 "Create util/set.go with a `StringSet` type: `func NewStringSet() *StringSet`, `Add(s string)` (duplicate adds are no-ops), `Has(s string) bool`, `Len() int`.",
 '''package t51

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestStringSet(t *testing.T) {
	s := util.NewStringSet()
	s.Add("a")
	s.Add("b")
	s.Add("a")
	if !s.Has("a") || !s.Has("b") || s.Has("c") {
		t.Fatalf("membership wrong: a=%v b=%v c=%v", s.Has("a"), s.Has("b"), s.Has("c"))
	}
	if got := s.Len(); got != 2 {
		t.Fatalf("Len = %d, want 2", got)
	}
}
''')

F["t52"] = ("FIFO queue", ["util/queue.go"],
 "Create util/queue.go with a `Queue` type for strings: `func NewQueue() *Queue`, `Push(s string)`, `Pop() (string, bool)` returning items first-in-first-out; Pop on an empty queue returns (\"\", false).",
 '''package t52

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestQueue(t *testing.T) {
	q := util.NewQueue()
	q.Push("a")
	q.Push("b")
	if v, ok := q.Pop(); !ok || v != "a" {
		t.Fatalf("first Pop = %q,%v, want a,true", v, ok)
	}
	if v, ok := q.Pop(); !ok || v != "b" {
		t.Fatalf("second Pop = %q,%v, want b,true", v, ok)
	}
	if v, ok := q.Pop(); ok || v != "" {
		t.Fatalf("empty Pop = %q,%v, want \\"\\",false", v, ok)
	}
}
''')

F["t53"] = ("LIFO stack", ["util/stack.go"],
 "Create util/stack.go with a `Stack` type for strings: `func NewStack() *Stack`, `Push(s string)`, `Pop() (string, bool)` returning items last-in-first-out; Pop on an empty stack returns (\"\", false).",
 '''package t53

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestStack(t *testing.T) {
	s := util.NewStack()
	s.Push("a")
	s.Push("b")
	if v, ok := s.Pop(); !ok || v != "b" {
		t.Fatalf("first Pop = %q,%v, want b,true", v, ok)
	}
	if v, ok := s.Pop(); !ok || v != "a" {
		t.Fatalf("second Pop = %q,%v, want a,true", v, ok)
	}
	if _, ok := s.Pop(); ok {
		t.Fatalf("empty Pop ok = true, want false")
	}
}
''')

F["t54"] = ("Email domain extraction", ["model/emaildomain.go"],
 "Create model/emaildomain.go with `func EmailDomain(e string) string`: the part after the last '@'; \"\" when e contains no '@'.",
 '''package t54

import (
	"testing"

	"bench/fleetsvc/model"
)

func TestEmailDomain(t *testing.T) {
	cases := [][2]string{
		{"a@b.co", "b.co"},
		{"weird@@x.io", "x.io"},
		{"@lead.io", "lead.io"},
		{"nodomain", ""},
		{"trail@", ""},
	}
	for _, c := range cases {
		if got := model.EmailDomain(c[0]); got != c[1] {
			t.Fatalf("EmailDomain(%q) = %q, want %q", c[0], got, c[1])
		}
	}
}
''')

F["t55"] = ("Min and max", ["util/minmax.go"],
 "Create util/minmax.go with `func MinInt(a, b int) int` and `func MaxInt(a, b int) int`.",
 '''package t55

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestMinMax(t *testing.T) {
	if got := util.MinInt(3, 7); got != 3 {
		t.Fatalf("MinInt = %d, want 3", got)
	}
	if got := util.MaxInt(3, 7); got != 7 {
		t.Fatalf("MaxInt = %d, want 7", got)
	}
	if got := util.MinInt(-2, -9); got != -9 {
		t.Fatalf("MinInt negatives = %d, want -9", got)
	}
}
''')

F["t56"] = ("Sums and means", ["util/sum.go"],
 "Create util/sum.go with `func SumInts(xs []int) int` and `func MeanInts(xs []int) int` — the sum divided by the length using Go's native integer division (truncated toward zero); an empty slice yields 0 for both.",
 '''package t56

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestSumMean(t *testing.T) {
	if got := util.SumInts([]int{1, 2, 3}); got != 6 {
		t.Fatalf("SumInts = %d, want 6", got)
	}
	if got := util.MeanInts([]int{1, 2, 4}); got != 2 {
		t.Fatalf("MeanInts = %d, want 2 (7/3 truncated)", got)
	}
	if got := util.MeanInts([]int{-1, -2}); got != -1 {
		t.Fatalf("MeanInts negatives = %d, want -1 (-3/2 truncated toward zero)", got)
	}
	if s, m := util.SumInts(nil), util.MeanInts(nil); s != 0 || m != 0 {
		t.Fatalf("empty: sum=%d mean=%d, want 0 0", s, m)
	}
}
''')

F["t57"] = ("String dedupe", ["util/dedupe.go"],
 "Create util/dedupe.go with `func DedupeStrings(xs []string) []string` keeping the first occurrence of each string, in order; an empty input yields a result of length 0.",
 '''package t57

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestDedupeStrings(t *testing.T) {
	got := util.DedupeStrings([]string{"b", "a", "b", "c", "a"})
	if len(got) != 3 || got[0] != "b" || got[1] != "a" || got[2] != "c" {
		t.Fatalf("DedupeStrings = %v, want [b a c]", got)
	}
	if got := util.DedupeStrings(nil); len(got) != 0 {
		t.Fatalf("DedupeStrings(nil) = %v, want length 0", got)
	}
}
''')

F["t58"] = ("String chunking", ["util/chunk.go"],
 "Create util/chunk.go with `func ChunkStrings(xs []string, n int) [][]string` splitting xs into consecutive chunks of n items, the last chunk possibly shorter; n <= 0 returns nil.",
 '''package t58

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestChunkStrings(t *testing.T) {
	got := util.ChunkStrings([]string{"a", "b", "c", "d", "e"}, 2)
	if len(got) != 3 || len(got[0]) != 2 || len(got[2]) != 1 || got[2][0] != "e" {
		t.Fatalf("ChunkStrings = %v, want [[a b] [c d] [e]]", got)
	}
	if got := util.ChunkStrings([]string{"a"}, 0); got != nil {
		t.Fatalf("n=0 = %v, want nil", got)
	}
}
''')

F["t59"] = ("Percentage calculation", ["util/percent.go"],
 "Create util/percent.go with `func PercentOf(part, whole int) int` returning part*100/whole using Go's native integer division; whole == 0 returns 0.",
 '''package t59

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestPercentOf(t *testing.T) {
	cases := [][3]int{{1, 4, 25}, {2, 3, 66}, {5, 5, 100}, {7, 0, 0}}
	for _, c := range cases {
		if got := util.PercentOf(c[0], c[1]); got != c[2] {
			t.Fatalf("PercentOf(%d,%d) = %d, want %d", c[0], c[1], got, c[2])
		}
	}
}
''')

F["t60"] = ("Median", ["util/median.go"],
 "Create util/median.go with `func MedianInt(xs []int) int`: sort a copy ascending (the input slice must not be modified); odd length returns the middle value, even length returns the lower of the two middle values; empty returns 0.",
 '''package t60

import (
	"testing"

	"bench/fleetsvc/util"
)

func TestMedianInt(t *testing.T) {
	if got := util.MedianInt([]int{5, 1, 3}); got != 3 {
		t.Fatalf("odd median = %d, want 3", got)
	}
	if got := util.MedianInt([]int{4, 1, 3, 2}); got != 2 {
		t.Fatalf("even median = %d, want 2 (lower middle)", got)
	}
	if got := util.MedianInt(nil); got != 0 {
		t.Fatalf("empty median = %d, want 0", got)
	}
	in := []int{9, 1}
	util.MedianInt(in)
	if in[0] != 9 || in[1] != 1 {
		t.Fatalf("input mutated: %v", in)
	}
}
''')
