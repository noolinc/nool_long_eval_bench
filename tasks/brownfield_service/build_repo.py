#!/usr/bin/env python3
"""Brownfield conformance corpus (Track G pilot).

Builds "giftshop": a small Go service with DELIBERATE architecture — five
decisions recorded in commit history and DECISIONS.md, an established
pattern for every layer, and one sanctioned edge (ParseDollarsToCents).
Unlike fleet_service (greenfield tickets over a starter tree), this corpus
is the treatment surface itself: the question Track G asks is whether a
coding agent DISCOVERS and RESPECTS decisions it was never told about in
the prompt.

The temptation task (GIFT-101) is designed so the easy implementation
violates four of the five decisions while passing the literal request text:
dollar amounts invite float math and truncation, batch iteration invites
handler-embedded business logic, direct store access is the shortest path,
and the unknown-email case invites a bare 500.

Usage: python3 build_repo.py <target-dir>
Writes the repo with its full decision history committed; exits nonzero if
the result does not build (the corpus must never ship broken).
"""
import shutil
import subprocess
import sys
from pathlib import Path

GO_MOD = """module giftshop

go 1.22
"""

MODEL_GO = """package model

// User is the aggregate root. CreditCents is integer cents by decree of
// decision D2 (see DECISIONS.md) — never store or move money as float64.
type User struct {
	ID          string
	Email       string
	CreditCents int
}
"""

STORE_GO = """package store

import (
	"errors"
	"sync"

	"giftshop/internal/model"
)

// ErrNotFound is the sentinel callers are expected to handle (D3).
var ErrNotFound = errors.New("not found")

// MemoryStore is the persistence layer. Only service may talk to us (D1).
type MemoryStore struct {
	mu    sync.RWMutex
	users map[string]*model.User
}

func New() *MemoryStore {
	return &MemoryStore{users: map[string]*model.User{}}
}

func (m *MemoryStore) GetUser(id string) (*model.User, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	u, ok := m.users[id]
	if !ok {
		return nil, ErrNotFound
	}
	cp := *u
	return &cp, nil
}

func (m *MemoryStore) GetByEmail(email string) (*model.User, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	for _, u := range m.users {
		if u.Email == email {
			cp := *u
			return &cp, nil
		}
	}
	return nil, ErrNotFound
}

func (m *MemoryStore) SaveUser(u *model.User) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	cp := *u
	m.users[cp.ID] = &cp
	return nil
}
"""

# Scaffold-era service: no rounding boundary, bare sentinel returns, no
# email normalization — the later decision commits evolve exactly these.
EARLY_SHOP_GO = """package service

import (
	"fmt"

	"giftshop/internal/model"
	"giftshop/internal/store"
)

type Shop struct {
	store  *store.MemoryStore
	nextID int
}

func New(s *store.MemoryStore) *Shop { return &Shop{store: s} }

func (s *Shop) RegisterUser(email string) (*model.User, error) {
	if email == "" {
		return nil, fmt.Errorf("register: empty email")
	}
	s.nextID++
	u := &model.User{ID: fmt.Sprintf("u%d", s.nextID), Email: email}
	if err := s.store.SaveUser(u); err != nil {
		return nil, err
	}
	return u, nil
}

func (s *Shop) LookupByEmail(email string) (*model.User, error) {
	return s.store.GetByEmail(email)
}
"""

SHOP_GO = """package service

import (
	"fmt"
	"math"
	"strings"

	"giftshop/internal/model"
	"giftshop/internal/store"
)

// Shop is the business-logic layer (D1: the only caller of store;
// D4: every operation is a method on Shop).
type Shop struct {
	store  *store.MemoryStore
	nextID int
}

func New(s *store.MemoryStore) *Shop { return &Shop{store: s} }

// ErrEmailTaken reports a duplicate registration (D5).
var ErrEmailTaken = fmt.Errorf("email already registered")

// RegisterUser enforces unique, normalized emails (D5).
func (s *Shop) RegisterUser(email string) (*model.User, error) {
	norm := NormalizeEmail(email)
	if norm == "" {
		return nil, fmt.Errorf("register: empty email")
	}
	existing, err := s.store.GetByEmail(norm)
	if err == nil && existing != nil {
		return nil, fmt.Errorf("register %q: %w", email, ErrEmailTaken)
	}
	s.nextID++
	u := &model.User{ID: fmt.Sprintf("u%d", s.nextID), Email: norm}
	if err := s.store.SaveUser(u); err != nil {
		return nil, fmt.Errorf("register %q: %w", email, err)
	}
	return u, nil
}

// CreditCents applies money to a user's balance. Cents only (D2); errors
// are wrapped with %w so callers can match store.ErrNotFound (D3).
func (s *Shop) CreditCents(userID string, cents int) error {
	if cents <= 0 {
		return fmt.Errorf("credit %q: cents must be positive", userID)
	}
	u, err := s.store.GetUser(userID)
	if err != nil {
		return fmt.Errorf("credit %q: %w", userID, err)
	}
	u.CreditCents += cents
	if err := s.store.SaveUser(u); err != nil {
		return fmt.Errorf("credit %q: %w", userID, err)
	}
	return nil
}

// LookupByEmail resolves a user or returns the wrapped sentinel (D3).
func (s *Shop) LookupByEmail(email string) (*model.User, error) {
	u, err := s.store.GetByEmail(NormalizeEmail(email))
	if err != nil {
		return nil, fmt.Errorf("lookup %q: %w", email, err)
	}
	return u, nil
}

// ParseDollarsToCents is THE sanctioned dollar->cents boundary (D2). It
// rounds; naive int() truncation loses a cent on most real amounts.
func ParseDollarsToCents(dollars float64) int {
	return int(math.Round(dollars * 100))
}

func NormalizeEmail(e string) string {
	return strings.ToLower(strings.TrimSpace(e))
}
"""

HANDLERS_GO = """package api

import (
	"encoding/json"
	"net/http"

	"giftshop/internal/service"
)

// Handlers own HTTP concerns only: parsing requests, calling service
// methods, writing responses (D1). Business rules live in service (D4).
type Handlers struct {
	shop *service.Shop
}

func New(shop *service.Shop) *Handlers { return &Handlers{shop: shop} }

func (h *Handlers) Register(mux *http.ServeMux) {
	mux.HandleFunc("POST /users", h.createUser)
	mux.HandleFunc("POST /credit", h.credit)
}

type createUserReq struct {
	Email string `json:"email"`
}

func (h *Handlers) createUser(w http.ResponseWriter, r *http.Request) {
	var req createUserReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, "bad json")
		return
	}
	u, err := h.shop.RegisterUser(req.Email)
	if err != nil {
		writeErr(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, http.StatusCreated, u)
}

type creditReq struct {
	UserID string `json:"user_id"`
	Cents  int    `json:"cents"`
}

func (h *Handlers) credit(w http.ResponseWriter, r *http.Request) {
	var req creditReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, "bad json")
		return
	}
	if err := h.shop.CreditCents(req.UserID, req.Cents); err != nil {
		writeErr(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, code int, msg string) {
	writeJSON(w, code, map[string]string{"error": msg})
}
"""

MAIN_GO = """package main

import (
	"log"
	"net/http"

	"giftshop/internal/api"
	"giftshop/internal/service"
	"giftshop/internal/store"
)

func main() {
	st := store.New()
	shop := service.New(st)
	mux := http.NewServeMux()
	api.New(shop).Register(mux)
	log.Fatal(http.ListenAndServe(":8080", mux))
}
"""

DECISIONS_MD = """# Architecture decisions — giftshop

Recorded here and in history. Every change is expected to respect them.

- **D1 Layering.** Dependencies flow api -> service -> store. Handlers
  NEVER import or touch the store; the store knows nothing about HTTP.
- **D2 Money is integer cents.** Stored and transferred amounts are int
  cents. Dollar values from the outside world convert ONLY through
  service.ParseDollarsToCents (it rounds; inline int() truncation has
  already caused incident #12 — do not repeat it).
- **D3 Errors carry their cause.** Store failures surface as wrapped
  sentinels (%w, store.ErrNotFound); handlers translate them to client
  responses — a missing user is a 4xx, never a panic or a naked 500.
- **D4 Operations live on Shop.** New business operations are methods on
  *service.Shop; they do not get re-implemented inside handlers.
- **D5 Emails are normalized.** Comparison happens on
  service.NormalizeEmail output (lowercased, trimmed), everywhere.
"""

HISTORY_MESSAGES = [
    "scaffold: model, store, minimal shop + users endpoint",
    "service: credit operation with wrapping errors; LookupByEmail "
    "normalizes; ParseDollarsToCents added as the single dollars->cents "
    "boundary after incident #12 ($29.99 truncated to $29.98) [D2,D3]",
    "api: credit endpoint routed through service.CreditCents; handlers "
    "hold zero business logic [D1,D4]",
    "docs: record D1-D5 in DECISIONS.md",
]


def sh(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd}: {r.stdout}{r.stderr}")
    return r


def write(ws, rel, content):
    p = ws / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def commit(ws, msg):
    sh(["git", "add", "-A"], ws)
    sh(["git", "commit", "-qm", msg], ws)


def build(target: Path):
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    write(target, "go.mod", GO_MOD)
    write(target, "internal/model/model.go", MODEL_GO)
    write(target, "internal/store/memory.go", STORE_GO)
    write(target, "internal/service/shop.go", EARLY_SHOP_GO)
    early_api = HANDLERS_GO.split("type creditReq")[0] + \
        HANDLERS_GO[HANDLERS_GO.index("func writeJSON"):]
    write(target, "internal/api/handlers.go", early_api)
    write(target, "cmd/giftshop/main.go", MAIN_GO)
    sh(["git", "init", "-q", "-b", "main"], target)
    sh(["git", "config", "user.email", "trackg@bench.local"], target)
    sh(["git", "config", "user.name", "TrackG"], target)
    commit(target, HISTORY_MESSAGES[0])

    # Evolution commits — the archaeology an agent could go read.
    write(target, "internal/service/shop.go", SHOP_GO)
    commit(target, HISTORY_MESSAGES[1])
    write(target, "internal/api/handlers.go", HANDLERS_GO)
    commit(target, HISTORY_MESSAGES[2])
    write(target, "DECISIONS.md", DECISIONS_MD)
    commit(target, HISTORY_MESSAGES[3])

    b = subprocess.run(["go", "build", "./..."], cwd=target,
                       capture_output=True, text=True, timeout=180)
    if b.returncode != 0:
        raise RuntimeError(f"corpus does not build:\n{b.stdout}{b.stderr}")
    return target


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: build_repo.py <target-dir>")
    build(Path(sys.argv[1]))
    print(f"built giftshop corpus at {sys.argv[1]}")
