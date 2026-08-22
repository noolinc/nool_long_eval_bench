# Pre-registration integrity

The design spec / pre-registration is:
`2026-08-20-nool-benchmark-suite-design.md`

    SHA-256: 659aec5611db3047a2db9a7321babbb2f62ad30db1561f5223b5d930bcaa14ef

## Why this file exists

Pre-registration claims rest on "hypotheses and predictions were committed
before the data was collected." That is verifiable here only through this
repository's own git/Knot history — which a skeptic can reasonably discount,
because the same party controls both. This file makes tampering detectable:

- The hash above pins the exact spec text that predictions reference.
- Amendments are appended to the spec (dated, with what changed), never
  edited silently. If the hash above stops matching the file, the spec was
  modified after pinning, and every prediction dated after 2026-08-22 must
  be treated as un-pre-registered.

## Verify

    shasum -a 256 docs/superpowers/specs/2026-08-20-nool-benchmark-suite-design.md

## Limitation (disclosed)

A self-published hash is still self-published. For paper-grade claims, the
hash should also be registered with an external timestamping service
(e.g. OpenTimestamps, or OSF Registries) so an independent party holds it.
Until that is done, treat the git-history ordering as evidence of process
discipline, not cryptographic proof of timing.
