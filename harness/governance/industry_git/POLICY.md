# Engineering policy — safe evolution of `bench/fleetsvc`

This policy states the rules every change to this repository must satisfy.
The **rules are identical regardless of tooling**; what differs between
setups is *which mechanism enforces them* (hosted CI + review app, or a
governed semantic VCS). The benchmark harness measures exactly that
difference.

## 1. Landing rules

- `main` must always build and pass `go vet ./...` and `go test ./...`
  (required checks; see `.github/workflows/ci.yml`).
- Changes land via merge queue in submission order. A merge that fails a
  required check is rejected and retried after the tree is green.
- Merge conflicts abort the merge; the ticket is re-submitted against the
  updated base. Conflict resolution by hand is out of policy for agents.

## 2. Ownership

- Paths in `CODEOWNERS` require the owning role's approval.
- Security-sensitive surfaces (`billing`, auth/identity) additionally
  require a security sign-off before push.

## 3. Change hygiene

- Commits follow Conventional Commits (`feat:`, `fix:`, ...).
- Exported functions carry tests (advisory lint, see pre-commit config).
- Credentials or private key material must never be committed — blocking,
  non-negotiable (enforced locally by secret scanning).

## 4. Recovery

- A landed change that breaks main is reverted (not patched forward) when
  the fix is not immediate.
- Later, unrelated work on main must survive any revert.

## 5. Provenance

- Every landed change is attributable to exactly one ticket and one author.
- Work landing under another writer's commit is an attribution defect.
