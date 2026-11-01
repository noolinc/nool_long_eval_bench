# Enterprise benchmarks and the build-versus-buy decision

This extension evaluates the review supplied on 2026-11-01 against the repository
and the installed **Nool 7.23.0 Enterprise** CLI (`cb59fd9d`, clean release build).
The original review is a local artifact named `nool-benchmark-analysis.md`; it is
not a pre-registration or evidence of product behavior. The protocols and historical
results remain unchanged. There is no defensible basis for its aggregate “3/10” score.

## Corrections to the review

Nool is a semantic VCS and governance/coordination substrate, with an agent harness.
The experiment's primary question is whether that substrate improves on a
**competitive conventional implementation**, not whether an agent can write code.

| Review assertion | Repository / CLI reality | Procurement implication |
|---|---|---|
| Four-worker limit | Existing fleet studies include N=25/35 and a pre-registered concurrency ladder | Measure adverse coordination cases against `git_competitive`, not only unscheduled Git |
| No economics | `analysis/cost_effectiveness.py` already prices failures, conflicts and poisoning | Add explicit ownership/maintenance/licence assumptions; do not invent token prices |
| Greenfield only; no handoff | `harness/brownfield_run.py` has architecture and interrupted-agent cells | Extend the existing pilot rather than claiming it doesn't exist |
| No scale probe | B10 generates up to 10,000 packages with dependency closures and test-selection oracles | Complement it with measured source dimensions and context navigation; neither proves success on a real monorepo |
| B10 is three self-healing/fixture tests | Actual B10 is admission cost versus repository size and semantic change surface | Preserve its independent R/S design |
| No CI/audit/review capability | CLI has `attest`, `audit verify`, `approval`, `approve`, `pr summary`, and impact-scoped `test select` | Test those mechanisms; hosted integration still needs independent qualification |
| B11 is a generic 1,000-message load test | Existing B11 compares bus builds on lease wake, pickup, retry effects and seal latency | Do not relabel those measurements as messaging capacity |
| Compliance framework testing implies compliance | Audit controls report partial, unverified and out-of-scope evidence | Never equate a signed audit report with certification, residency or PII protection |

## Implemented profile

From the repository root, with Python 3, Git, Go and a licensed Nool CLI on PATH:

```sh
make -f enterprise/Makefile test
make -f enterprise/Makefile smoke
# Opt-in capacity run; potentially expensive CPU/RAM/time, no LLM spend:
make -f enterprise/Makefile enterprise
```

The smoke profile is a plumbing check: 10 packages, three queries, four competing
clients. The enterprise profile generates **5,000 packages, 10,000 Go files,
110,000 production lines and 100,000 test functions**, performs 20 context queries,
and exercises 50 local lease clients. These are generated dimensions, **not collected
enterprise-scale results**. Both profiles execute the complete generated Go test
suite, measure initialization separately, alternate query arm order, and preserve
each command's exit code, stdout, stderr and duration. No p99 or SLA claim is made
from these samples. The first query includes any cold query-cache effects.

| Scenario | Observable checks | Build counterpart / interpretation |
|---|---|---|
| `scale` | Exact production/test file oracle, context token-budget estimate, init/query/full-suite latency, measured files/LOC/test counts | Same query and fixture with `git grep`; exact-symbol search is a deliberately strong conventional baseline. Independent Go packages do not model a coupled polyglot monorepo |
| `governance` | Real Go tests; independent trusted CI receipts satisfy obligations; developer's receipt doesn't; injected trusted failure receipt revokes pass; correction restores it; receipts leave branch HEAD fixed | A build alternative needs CI identity, signed receipts and required-check enforcement. This probe tests Nool's proof matrix, not hosted branch protection or push enforcement |
| `governance` audit | Clone without local ledger reproduces control outcomes; imported history integrity is scored separately; signed export verifies under explicit test anchor; altered report is rejected | Git history plus detached refs are the transport. An identical failed audit is reproducible but still fails the integrity check |
| `approval` | Pending request prevents landing; self-review rejected; wrong role can't approve; authorized independent key approves; candidate resumes and tests pass | A build alternative needs CODEOWNERS plus an **enforced** approval queue. Local scripted keys don't establish reviewer satisfaction, SSO or cross-machine correctness |
| `coordination` | All disjoint leases admitted; exactly one winner for a shared scope; other clients return contention | Local admission pressure only. Existing competitive fleet arms measure edits/merges, retries, wasted agent spend and integrated health |

Use `python3 -m enterprise.run --help` to select scenarios, a frozen `--nool` binary,
command timeout or output path. Default scratch results go to `work/enterprise/`.
Each result records CLI build metadata, binary and runner SHA-256 hashes, UTC times,
platform, fixture hash and all attempted scenarios. Binary replacement invalidates
the run. Failed checks and unsupported/edition-gated commands make the process fail;
they are retained in the result, never silently counted as a pass.

Workspaces and HOME are disposable. Only the operator's local licence config and
device identifier are copied; test keys are public fixed fixtures. No identity key,
provider credential file or agent instructions are copied. The profile does not
invoke models or publish to a remote service. It is **not an air-gap/egress test**:
it does not enforce a network boundary. Existing global environment/toolchain state
can still affect local timings. Compare load and hardware before citing latency.

The mechanism suite intentionally does not assign a composite readiness score or
claim a causal product win against Git. It has no paired implementation of a
complete conventional approval/audit service. Quantify that service's operational
cost using buyer inputs and matched fleet evidence below.

## Ownership economics

```sh
# Copy and edit the example for the buyer. Every dollar/hour is hypothetical.
python3 -m enterprise.decision \
  --assumptions enterprise/assumptions.example.json \
  --build-arm git_competitive --buy-arm nool_try \
  --output work/enterprise/decision.json
```

This separately reports measured agent cost and healthy delivery against **assumed**
annual workload, loaded engineering rate, repair hours, initial integration effort,
amortization period, ongoing maintenance, infrastructure and annual licence quote.
The example's $12,000 licence fee is an illustration, not a Nool price or quote.

For each arm, annual TCO is:

```
annual tickets × (observed LLM spend / offered tickets
                  + observed failure fraction × assumed repair hours × hourly rate)
+ setup hours / amortization years × hourly rate
+ annual maintenance hours × hourly rate
+ annual infrastructure + annual licence
```

The decision unit is offered workload, including failed attempts and retries.
Healthy accepted output requires both ticket acceptance and a healthy final main.
The report also gives measured LLM dollars per healthy acceptance and the annual
licence fee at which the two scenarios break even. A negative break-even fee means
buying cannot break even under those inputs even at zero licence cost. Wall time is
reported separately and **never billed as engineering labor**. Repair effort is a
sensitivity input, not an observed productivity improvement.

Cells match repository, language/source kind, corpus, starter hash, commands, protocol hash,
footprint source/noise, worker count, harness, requested and reported model, ticket set/tier/limit and Nool
version. Ten independent run replicates per arm are required by default. The unit
is the run, not individual tickets. This is descriptive scenario analysis, without
confidence intervals or a causal ROI claim. Sparse or unmatched cells say
`insufficient_evidence`; the tool never selects a winner in their absence.
Scripted runs, duplicate IDs, suspect acceptance without landing, missing metadata,
unknown native session cost, unreconciled run totals and runs disqualified by
unmatched steering gates are excluded with reasons.
All retry sessions must be present in native agent accounting. The input files are
hashed. Historical records lacking those fields cannot support a procurement ROI
claim just because a legacy total happens to be non-null.

## Evidence still required before a purchase conclusion

| Buyer question | Existing / new executable coverage | Remaining qualification |
|---|---|---|
| Better than what we can build? | `git_competitive` versus `nool_try`/`nool_gated`; new ownership scenario calculator | Matched repeated runs on buyer workloads; measured build-team implementation and maintenance effort; actual quote |
| Works in our codebase? | B9 language adapters, B10 dependent-package scaling, new source-size/navigation fixture, brownfield pilot | Pinned real 100K+ LOC corpus, meaningful cross-service tasks, polyglot/build-system coverage and full regression protection |
| Fits our delivery chain? | Local real tests → trusted attestation; approval → resume; audit clone replay | Hosted PR/MR creation/update, required checks, merge queues, Jira/Linear and notifications. `pr summary` renders context; it doesn't create a PR |
| Enforces our controls? | Trusted versus untrusted receipts, independent review, tampered report rejection | Revocation, path-scoped authority, policy bypass/push negative controls, pinned trust root, branch protection and org identity integration |
| Safe for regulated data? | Audit evidence explicitly reports gaps | Measured secret/PII precision and recall, malicious payload corpus, egress/residency enforcement, retention/deletion, licence compliance; legal framework mapping |
| Survives a working day? | B3 recovery, B11 retry/wake probes, brownfield handoff pilot | Process-kill/disk-full/429/provider-outage injection, restart idempotence, multi-hour soak, lost-response duplicate prevention and recovery time distributions |
| Improves agent quality? | Existing independent acceptance and final health scoring | Same-model repeated agent runs, reviewer feedback transfer and determinism; mechanism repetitions are not coding-agent repetitions |

These remaining checks are explicit gaps, not unsupported “passes” or marketing
claims. Keep the frozen fleet-v4 protocol unchanged; preregister new corpus and
fault-injection studies before collecting procurement evidence.

## First local validation (2026-11-01)

Cross-track context and the other benchmark outcomes are summarized in the
[2026-11-01 results overview](findings/2026-11-01-benchmark-results.md).

The included smoke artifact is
[`results/enterprise/2026-11-01-smoke.json`](../results/enterprise/2026-11-01-smoke.json).
It is deterministic mechanism evidence on one machine, not an LLM/fleet replication
or the full enterprise profile. Nool 7.23.0 reports `parent_missing` in imported
fixture history, and both the original repository and a fresh clone reproduce it.
The smoke profile passes 35 of 36 checks; the governance scenario fails its
imported-history integrity check. Scale/context (10/10), approval (8/8), and
the four-client coordination check (3/3) pass.
Retain that failure for vendor investigation; do not waive it to make the profile
green. The artifact contains the exact IDs and complete CLI diagnostics.

The separate
[`50-client lease artifact`](../results/enterprise/2026-11-01-50-client-leases.json)
executes the enterprise profile's coordination scenario only. It does not run
the 110K-line scale fixture or establish fleet/user throughput. Its 50-client
lease probe passes all three checks, but it is not a long-running load test.
