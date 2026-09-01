# QuantForge Engineering Log

This file records meaningful engineering history.

Use it for:

* BUG
* FIX
* DECISION
* DISCOVERY
* PERFORMANCE
* DEBT

Historical entries should not be deleted after an issue is resolved.

---

## ID Conventions

Bugs:

`BUG-001`

Decisions:

`DECISION-001`

Performance findings:

`PERF-001`

Technical debt:

`DEBT-001`

Discoveries:

`DISCOVERY-001`

---

## Bug Template

### BUG-XXX — Short Description

Date:
Status: Open / Fixed / Deferred
Severity: Low / Medium / High / Critical
Component:
Related Spec:

#### Observed Behavior

Describe what happened.

#### Expected Behavior

Describe what should have happened.

#### Root Cause

Describe the underlying cause when known.

#### Fix

Describe the implemented correction.

#### Regression Test

Record the exact regression test.

#### Files Changed

* ...

#### Related Commit

TBD

---

## Decision Template

### DECISION-XXX — Short Description

Date:
Status: Proposed / Accepted / Superseded
Related Spec:

#### Context

What engineering choice had to be made?

#### Options Considered

1. ...
2. ...

#### Decision

What was selected?

#### Reasoning

Why?

#### Consequences

Positive:

* ...

Negative:

* ...

---

## Performance Template

### PERF-XXX — Short Description

Date:
Related Spec:

#### Workload

Describe the benchmark dataset and workload.

#### Baseline

Runtime:
Memory:
Throughput:

#### Change

Describe optimization.

#### Result

Runtime:
Memory:
Throughput:

#### Environment

Record relevant hardware/software information.

#### Benchmark Command

`...`

---

## Technical Debt Template

### DEBT-XXX — Short Description

Date:
Status: Open / Scheduled / Resolved
Component:
Related Spec:

#### Current Limitation

...

#### Why It Exists

...

#### Risk

...

#### Proposed Resolution

...

---

# Entries

## DECISION-001 — Establish the Repository Foundation Toolchain

Date: 2026-08-31
Status: Accepted
Related Spec: SPEC-001

### Context

QuantForge needed an installable, typed, and testable Python foundation before financial subsystems were introduced.

### Options Considered

1. Use a minimal `src/`-layout package with one configured quality tool per responsibility.
2. Introduce a larger application framework and broader dependency set immediately.

### Decision

Use Python 3.12, Hatchling, pytest, Ruff, strict mypy, and a pinned GitHub Actions quality gate. Keep runtime dependencies empty.

### Reasoning

This is the smallest toolchain that provides packaging, deterministic tests, linting, formatting, and static type checking without constraining later financial designs.

### Consequences

Positive:

* The package installs from the `src/` layout.
* Local and CI quality commands are explicit.
* No finance, data, web, or machine-learning dependency was introduced prematurely.

Negative:

* Developers must install the pinned development dependency group.
* Pinned tool versions require deliberate maintenance as Python and the tools evolve.

---

## DECISION-002 — Use Standard-Library Structured Logging

Date: 2026-08-31
Status: Accepted
Related Spec: SPEC-001

### Context

The repository foundation required structured logging while keeping dependencies minimal.

### Options Considered

1. Implement JSON formatting with Python's standard `logging` package.
2. Add a third-party structured logging framework.

### Decision

Provide opt-in JSON logging through `quantforge.logging` using only the Python standard library.

### Reasoning

The required core fields and deterministic behavior do not yet justify another runtime dependency.

### Consequences

Positive:

* Structured output is available with no runtime dependency.
* Importing `quantforge` does not mutate global logging configuration.

Negative:

* Advanced context binding and processor pipelines are not available yet.

---

## DECISION-003 — Establish Permanent Documentation Sources of Truth

Date: 2026-08-31
Status: Accepted
Related Spec: Project-wide

### Context

QuantForge needed durable documentation for project intent, architecture, implementation order, specifications, and engineering history.

### Options Considered

1. Maintain explicit permanent documents with distinct responsibilities.
2. Keep project guidance distributed across ad hoc prompts and short placeholder files.

### Decision

Use `docs/PROJECT_SPEC.md`, `ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/specs/`, `docs/ENGINEERING_LOG.md`, and `README.md` as the documented sources of truth defined in `AGENTS.md`.

### Reasoning

Explicit ownership makes disagreements discoverable and supports specification-driven development.

### Consequences

Positive:

* Project scope and subsystem boundaries are visible before implementation.
* Specifications and engineering decisions have stable locations.

Negative:

* Documentation must be maintained when approved architecture or project intent changes.

---

## DISCOVERY-001 — Python 3.12 Foundation Validation Became Available Locally

Date: 2026-08-31
Related Spec: SPEC-001

### Finding

The first SPEC-001 validation used Python 3.14.3 because Python 3.12 was not available in the local environment. A later full validation during the permanent-documentation update ran successfully on Python 3.12.14.

### Impact

The foundation's tests, Ruff checks, formatting checks, and strict mypy checks have now passed locally on the declared Python 3.12 target in addition to the newer interpreter.

---

## DECISION-004 — Represent Canonical Market Bars with a Frozen Slotted Dataclass

Date: 2026-08-31
Status: Accepted
Related Spec: SPEC-002

### Context

QuantForge needs one typed OHLCV representation that cannot leak provider or storage details into downstream systems.

### Options Considered

1. Use mutable dictionaries.
2. Add a validation framework such as Pydantic.
3. Use a frozen, slotted standard-library dataclass with explicit validation.

### Decision

Expose `quantforge.domain.Bar` as `@dataclass(frozen=True, slots=True)`. Normalize symbols during construction and explicitly distinguish incorrect fundamental types from invalid domain values.

### Reasoning

The dataclass provides the specified immutability, equality, hashing, type annotations, and low object overhead without adding a runtime dependency. Explicit construction-time validation keeps the canonical boundary deterministic and rejects invalid data before it reaches later systems.

### Consequences

Positive:

* Providers and storage implementations can target one small canonical type.
* Valid bars are immutable, hashable, and deterministic.
* Runtime dependencies remain empty.

Negative:

* Prices use binary floating-point as approved by SPEC-002.
* Bar frequency, serialization, adjusted values, and exchange-session semantics remain intentionally unspecified.

---

## DECISION-005 — Keep CSV Parsing Separate from Bar Domain Validation

Date: 2026-09-01
Status: Accepted
Related Spec: SPEC-003

### Context

The first file-based market-data adapter must parse CSV input without duplicating canonical financial rules or requiring whole-dataset memory.

### Options Considered

1. Load complete files with a dataframe dependency.
2. Parse CSV rows and duplicate OHLCV validation in the provider.
3. Stream rows with the standard library, convert textual types, and construct the existing canonical `Bar`.

### Decision

Implement `quantforge.data.csv.CSVMarketDataProvider` with the standard-library CSV reader and generator-based iteration. The provider validates headers, converts text to `datetime`, `float`, and `int`, adds CSV line context, and delegates all bar-level domain validation to `Bar`.

### Reasoning

This maintains one owner for financial invariants, preserves exception causes and row provenance during failures, avoids a runtime dependency, and permits consumers to process large files incrementally.

### Consequences

Positive:

* CSV rows cannot bypass the canonical `Bar` boundary.
* Row order and duplicates are preserved exactly.
* File access and parsing remain lazy and network-independent.

Negative:

* Only the canonical lowercase CSV schema is supported.
* Cross-row validation, sorting, deduplication, and repair are intentionally unavailable.
* No generic provider interface exists until requirements from another provider are known.
