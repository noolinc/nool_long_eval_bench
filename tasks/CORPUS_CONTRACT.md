# Cross-repository fleet corpus contract

Each corpus lives under `tasks/<task-root>/` and contains:

- `starter/`: the clean repository state;
- `STARTER_SHA256`: deterministic hash of `starter/`;
- a ticket JSON file;
- `accept/<ticket-id>/`: held-out acceptance assets copied only at scoring.

The ticket JSON must declare `corpus`, `language`, `repository`,
`source_kind`, `footprint_source`, `commands`, and `tickets`. Commands are
argument arrays rather than shell strings. The acceptance command contains
`{ticket}`, expanded by the harness after copying that ticket's acceptance
assets to `accept/<ticket-id>/`. `footprint_source` distinguishes
`author-oracle`, `static-prediction`, and `model-prediction`; noise applied by
the harness is recorded separately.

Example command block:

```json
{
  "commands": {
    "build": ["go", "build", "./..."],
    "test": ["go", "test", "./..."],
    "accept": ["go", "test", "./accept/{ticket}/"]
  }
}
```

Imported benchmark tasks must retain the upstream prompt and acceptance
criteria byte-for-byte. Record their upstream repository, revision, task ID,
license, and content hash in the corpus metadata. A converter may normalize
paths and command invocation, but must not rewrite the task itself.

`source_kind` is one of `synthetic`, `historical`, or `external-benchmark`.
Synthetic translations across languages are controlled mechanism corpora;
they must not be described as independent real-repository evidence.
