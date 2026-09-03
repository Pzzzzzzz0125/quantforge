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

---

## DECISION-006 — Keep Dataset Validation Diagnostic and Single-Pass

Date: 2026-09-01
Status: Accepted
Related Spec: SPEC-004

### Context

Canonical bars can be individually valid while a streamed dataset still contains duplicate
observations or timestamps that are out of order within a symbol.

### Options Considered

1. Materialize, sort, deduplicate, or repair the dataset during validation.
2. Stop at the first data-quality issue by raising an exception.
3. Consume bars once and collect immutable diagnostic issues without changing observations.

### Decision

Implement `MarketDataValidator` as a one-pass diagnostic consumer. Retain observation keys for
duplicate detection, the maximum timestamp observed per symbol for ordering checks, and summary
state. Return findings in discovery order through immutable `ValidationIssue` and
`ValidationReport` objects. Reserve `TypeError` for violations of the `Iterable[Bar]` input
contract.

### Reasoning

Diagnostic output preserves research inputs and exposes all discovered structural defects in one
run. Per-symbol state supports interleaved streams without sorting, and retaining seen keys is the
minimum exact state needed for duplicate detection.

### Consequences

Positive:

* Lists, tuples, generators, and the streaming CSV iterator share one validation path.
* Data-quality findings are deterministic, structured, and do not mutate input.
* Runtime dependencies remain empty.

Negative:

* Exact duplicate detection requires O(n) memory in the worst case.
* Trading-session gaps, frequency, corporate actions, and price anomalies remain intentionally
  unvalidated.

---

## BUG-001 — Cascading Out-of-Order Bars Could Be Missed

Date: 2026-09-01
Status: Fixed
Severity: Medium
Component: Market data validation
Related Spec: SPEC-004

### Observed Behavior

After timestamps `09:30`, `09:35`, and `09:32` for one symbol, the validator replaced its ordering
reference with `09:32`. A subsequent `09:34` was therefore accepted even though it still followed
the already observed `09:35`.

### Expected Behavior

Both `09:32` and `09:34` should produce `out_of_order_timestamp` issues because both are below the
maximum timestamp already observed for the symbol.

### Root Cause

The validator tracked the immediately preceding timestamp instead of the maximum timestamp seen
so far for each symbol.

### Fix

Track a per-symbol maximum timestamp, compare each observation to that maximum using strict `<`,
and update the maximum only when a later timestamp is observed.

### Regression Test

`test_cascading_out_of_order_timestamps_are_compared_with_observed_maximum`

### Files Changed

* `src/quantforge/data/validation.py`
* `tests/test_market_data_validation.py`
* `docs/specs/SPEC-004-market-data-validation.md`
* `docs/ENGINEERING_LOG.md`

### Related Commit

TBD

---

## DECISION-007 — Use a Versioned PyArrow Schema with UTC Parquet Persistence

Date: 2026-09-01
Status: Accepted
Related Spec: SPEC-005

### Context

QuantForge needs typed, efficient local persistence for canonical bars while preserving the
domain boundary, supporting streamed inputs, and avoiding a dataframe or database dependency.

### Options Considered

1. Continue using CSV as the primary research storage format.
2. Add Pandas alongside a Parquet engine.
3. Use PyArrow directly with one canonical, versioned Arrow schema.

### Decision

Pin PyArrow 25.0.1 as the sole runtime dependency for SPEC-005. Persist market bars with a
centrally defined schema containing non-null string, `timestamp[us, UTC]`, float64, and int64
fields plus explicit schema-version metadata. Normalize timestamps to UTC, process records in
bounded batches, and publish same-directory temporary files through atomic replacement.

### Reasoning

Direct PyArrow use provides native typed Parquet reads and writes without introducing Pandas,
Polars, or DuckDB. A versioned schema prevents silent coercion, UTC normalization gives one stable
storage representation for timestamp instants, and atomic publication protects research datasets
from partial writes.

### Consequences

Positive:

* Persisted market-bar files have explicit types and compatibility metadata.
* One-pass CSV and generator inputs can be stored without whole-dataset materialization.
* Readers reconstruct the existing `Bar` domain type rather than exposing Arrow records.
* Existing files are protected unless overwrite is explicitly requested.

Negative:

* PyArrow is a substantial binary runtime dependency that requires deliberate version updates.
* Original timezone names and offsets are intentionally normalized to UTC.
* SPEC-005 supports one local file only; partitioning and dataset cataloging remain unimplemented.

---

## DECISION-008 — Use Immutable Records and Exact Artifact Fingerprints

Date: 2026-09-03
Status: Accepted
Related Spec: SPEC-006

### Context

Persisted Parquet files need stable research identities, portable locations, provenance, and a
way to detect byte-level drift without conflating those separate concepts or introducing a
database.

### Options Considered

1. Treat filenames or absolute paths as dataset identity.
2. Store mutable records in SQLite or another catalog backend.
3. Assign UUID-based IDs and persist immutable records in versioned JSON with relative paths and
   SHA-256 fingerprints.

### Decision

Use immutable `DatasetRecord` values with generated `ds_<uuid4 hex>` IDs, catalog-relative POSIX
storage paths, independent provenance text, exact incremental SHA-256 fingerprints, and atomic
versioned UTF-8 JSON persistence. Registration streams summary metadata through the existing
`ParquetMarketDataStore` boundary and does not invoke dataset-quality validation.

### Reasoning

Independent identity, location, integrity, and provenance fields make dataset references stable
and auditable. Relative paths survive repository relocation, exact hashes expose artifact drift,
and atomic JSON replacement provides a reviewable local catalog without another runtime
dependency.

### Consequences

Positive:

* Dataset IDs remain stable when repository paths move.
* Exact artifact changes are detectable without modifying registered records.
* Existing Parquet schema and domain validation remain centralized in the storage adapter.
* Catalog files are human-readable, versioned, and atomically updated.

Negative:

* Registration scans Parquet rows and separately hashes every artifact byte.
* The whole catalog is loaded and rewritten for each new registration.
* Concurrent multi-process writers are not coordinated in version 1.
