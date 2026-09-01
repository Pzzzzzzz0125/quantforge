# SPEC-004 — Market Data Validation

Status: Completed
Owner: Paul
Created: 2026-09-01
Updated: 2026-09-01

## 1. Problem

QuantForge can now construct canonical `Bar` objects and stream them from canonical CSV files.

Individual `Bar` validation is insufficient to determine whether a collection of market observations is structurally suitable for research.

A dataset may contain individually valid bars while still containing:

* duplicate observations;
* out-of-order timestamps within a symbol;
* unexpected dataset structure.

QuantForge needs a deterministic dataset-level validation layer that detects and reports these issues without silently modifying the underlying data.

---

## 2. Goal

Implement a market-data validator that consumes an iterable of canonical `Bar` objects and produces a structured `ValidationReport`.

The validator must initially detect:

* duplicate `(symbol, timestamp)` observations;
* out-of-order timestamps within each symbol.

The report must also provide useful dataset summary statistics.

The validator must never silently:

* sort data;
* deduplicate data;
* drop observations;
* repair timestamps;
* alter prices.

---

## 3. Non-Goals

SPEC-004 does NOT implement:

* market-data repair;
* automatic sorting;
* automatic deduplication;
* exchange calendars;
* trading-session validation;
* missing-trading-day detection;
* missing-bar detection;
* market-frequency inference;
* corporate actions;
* stock splits;
* dividends;
* symbol changes;
* price-spike detection;
* stale-price detection;
* cross-symbol timestamp alignment;
* survivorship-bias analysis;
* external market-data providers;
* persistence;
* Parquet;
* DuckDB;
* feature computation;
* backtesting;
* strategies.

Those concerns belong to future specifications.

---

## 4. Background

### 4.1 Domain Validation vs Dataset Validation

SPEC-002 validates one `Bar`.

Examples:

* prices are positive;
* timestamps are timezone-aware;
* OHLC relationships are valid.

SPEC-004 validates relationships among multiple `Bar` objects.

Example:

```text
AAPL 09:30
AAPL 09:32
AAPL 09:31
```

All three bars may be individually valid while the sequence is out of order.

### 4.2 Validation Philosophy

The validator is diagnostic.

It detects and reports problems.

It does not mutate or repair input data.

This allows research pipelines to make explicit decisions about invalid datasets rather than silently changing historical observations.

---

## 5. Public Concepts

SPEC-004 should introduce:

* `ValidationIssue`
* `ValidationSeverity`
* `ValidationReport`
* `MarketDataValidator`

A similarly small and cohesive API is acceptable if implementation details justify it.

---

## 6. Validation Severity

The initial severity levels should be:

* `ERROR`
* `WARNING`

Duplicate observations and ordering violations are `ERROR`.

An empty dataset may produce a `WARNING`.

Severity should use an enum or equivalent stable typed representation.

---

## 7. Validation Issue

Each discovered issue should be represented explicitly.

Conceptual fields:

```python
ValidationIssue(
    code=...,
    severity=...,
    message=...,
    symbol=...,
    timestamp=...,
)
```

Fields that do not apply may be optional.

Issue codes should be machine-readable and stable.

Initial codes:

* `duplicate_observation`
* `out_of_order_timestamp`
* `empty_dataset`

Human-readable messages must also be provided.

---

## 8. Validation Report

The report should contain:

* total number of bars checked;
* number of unique symbols;
* earliest timestamp when available;
* latest timestamp when available;
* immutable collection of issues.

The report should expose:

```python
report.is_valid
```

`is_valid` is true when the report contains no `ERROR` issues.

Warnings do not make the report invalid.

Suggested convenience properties may include:

* `errors`
* `warnings`
* `error_count`
* `warning_count`

Do not add unnecessary reporting abstractions.

---

## 9. Market Data Validator

Preferred conceptual API:

```python
from quantforge.data.validation import MarketDataValidator

validator = MarketDataValidator()

report = validator.validate(bars)
```

where:

```python
bars: Iterable[Bar]
```

The validator must support one-pass iterables such as generators.

It must not require the caller to materialize the entire iterable into a list before validation.

---

## 10. Functional Requirements

### FR-1 — Accept Iterable of Bar

The validator must accept:

```python
Iterable[Bar]
```

including:

* list;
* tuple;
* generator;
* CSV provider iterator.

### FR-2 — Do Not Mutate Input

The validator must not modify any input object.

### FR-3 — Total Count

The report must record the exact number of bars consumed.

### FR-4 — Unique Symbol Count

The report must record the number of unique normalized symbols encountered.

### FR-5 — Timestamp Range

For non-empty datasets, record:

* earliest timestamp;
* latest timestamp.

These values are based on observed data, regardless of input ordering.

### FR-6 — Duplicate Detection

A duplicate exists when the same:

```text
(symbol, timestamp)
```

occurs more than once.

The first occurrence is accepted.

Each later occurrence must produce a duplicate issue.

The validator must not remove either observation.

### FR-7 — Per-Symbol Ordering

For each symbol independently, timestamps should be strictly increasing in encounter order.

Example valid input:

```text
AAPL 09:30
MSFT 09:30
AAPL 09:31
MSFT 09:31
```

Example invalid input:

```text
AAPL 09:30
AAPL 09:32
AAPL 09:31
```

The `09:31` observation must produce an ordering error.

### FR-8 — Duplicate vs Ordering

A repeated timestamp should be reported as a duplicate.

It should not also need to generate a separate ordering error solely because the timestamp equals the previous timestamp.

Avoid double-reporting the same structural defect unless distinct problems truly exist.

### FR-9 — Empty Dataset

An empty input iterable must produce a valid `ValidationReport` object.

The report should contain:

* `total_bars = 0`
* `unique_symbols = 0`
* no earliest timestamp
* no latest timestamp
* one `empty_dataset` warning

The report remains valid because warnings do not invalidate the dataset.

### FR-10 — Issue Ordering

Issues must appear deterministically in the order they are discovered while consuming input.

### FR-11 — Input Preservation

The validator must not:

* reorder observations;
* deduplicate observations;
* return repaired observations.

The primary output is the diagnostic report.

---

## 11. One-Pass Validation

The validator should process the iterable in one pass.

State may include:

```text
seen observations
latest timestamp observed per symbol
symbol set
global earliest timestamp
global latest timestamp
counts
issues
```

The validator must not convert the full iterable into a list solely for convenience.

Note:

Duplicate detection necessarily requires memory proportional to the number of unique `(symbol, timestamp)` keys encountered.

That tradeoff is acceptable in SPEC-004.

---

## 12. Proposed Internal State

A straightforward implementation may maintain:

```python
seen: set[tuple[str, datetime]]
maximum_timestamp_by_symbol: dict[str, datetime]
symbols: set[str]
```

and global summary variables.

This is guidance, not a mandatory implementation.

Prefer correctness and readability over unnecessary abstraction.

---

## 13. Data Model

### ValidationSeverity

Preferred:

```python
class ValidationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
```

### ValidationIssue

Should be immutable.

Potential fields:

```python
code: str
severity: ValidationSeverity
message: str
symbol: str | None
timestamp: datetime | None
```

### ValidationReport

Should be immutable once constructed.

Potential fields:

```python
total_bars: int
unique_symbols: int
earliest_timestamp: datetime | None
latest_timestamp: datetime | None
issues: tuple[ValidationIssue, ...]
```

Derived values such as `is_valid` should preferably be properties rather than mutable stored state.

---

## 14. Invariants

A valid report must satisfy:

* `total_bars >= 0`
* `unique_symbols >= 0`
* `unique_symbols <= total_bars` for non-empty bar datasets
* empty datasets have no earliest timestamp
* empty datasets have no latest timestamp
* non-empty datasets have both earliest and latest timestamps
* `earliest_timestamp <= latest_timestamp`
* `is_valid` is false if any issue has severity `ERROR`
* `is_valid` is true if no issue has severity `ERROR`

Validation must not change any `Bar`.

---

## 15. Error Handling

The validator expects canonical `Bar` objects.

Passing objects that are not `Bar` instances should fail clearly with `TypeError`.

Do not silently ignore invalid input types.

The validator itself should not catch unrelated programming exceptions and convert them into validation issues.

Validation issues represent data-quality findings, not internal software failures.

---

## 16. Edge Cases

Tests must include at least:

* empty iterable;
* one bar;
* multiple symbols;
* correctly ordered bars;
* interleaved correctly ordered symbols;
* exact duplicate;
* repeated duplicate more than twice;
* duplicate separated by other rows;
* out-of-order adjacent timestamp;
* out-of-order timestamp separated by another symbol;
* duplicate that equals last timestamp;
* earliest timestamp appearing late in the input;
* latest timestamp appearing early in the input;
* generator input;
* tuple input;
* list input;
* invalid non-Bar item;
* input bars remain unchanged;
* deterministic issue order.

---

## 17. Testing Plan

### Unit Tests

Test each:

* report field;
* severity;
* issue code;
* duplicate rule;
* ordering rule;
* empty dataset behavior;
* `is_valid`.

### Generator Test

Use a one-shot generator and verify validation succeeds without requiring replay.

### Integration Test

Feed:

```python
CSVMarketDataProvider(...).iter_bars()
```

directly into:

```python
MarketDataValidator().validate(...)
```

Verify dataset-level issues are detected.

This test should remain local and network-independent.

### Immutability Tests

Verify issues and reports cannot be mutated if immutable dataclasses are selected.

---

## 18. Acceptance Criteria

* [x] Structured market-data validation API exists.
* [x] `ValidationSeverity` supports ERROR and WARNING.
* [x] `ValidationIssue` is structured and immutable.
* [x] `ValidationReport` is structured and immutable.
* [x] `MarketDataValidator` accepts `Iterable[Bar]`.
* [x] one-shot generators are supported.
* [x] total bars are counted correctly.
* [x] unique symbols are counted correctly.
* [x] earliest timestamp is calculated correctly.
* [x] latest timestamp is calculated correctly.
* [x] duplicates are detected by `(symbol, timestamp)`.
* [x] later duplicate occurrences generate issues.
* [x] duplicates are not removed.
* [x] per-symbol ordering violations are detected.
* [x] valid interleaving across symbols is accepted.
* [x] duplicate equality is not unnecessarily double-reported as ordering failure.
* [x] empty dataset produces a warning.
* [x] empty dataset report remains valid.
* [x] ERROR issues make `is_valid` false.
* [x] WARNING-only reports remain valid.
* [x] issue ordering is deterministic.
* [x] validator does not sort or repair input.
* [x] invalid non-Bar items fail clearly.
* [x] integration with CSV iterator is tested.
* [x] no new runtime dependency is introduced.
* [x] pytest passes.
* [x] Ruff passes.
* [x] formatting passes.
* [x] strict mypy passes.
* [x] Markdown validation passes if configured.
* [x] `git diff --check` passes.
* [x] documentation and spec index are updated.

---

## 19. Performance Considerations

Validation should be one-pass.

Expected complexity:

```text
Time: O(n)
```

for `n` bars, assuming average constant-time set/dictionary operations.

Duplicate detection requires:

```text
Space: O(n)
```

in the worst case because previously observed `(symbol, timestamp)` keys must be retained.

This is acceptable for the first implementation.

Future large-scale validation may introduce:

* partitioned validation;
* database constraints;
* streaming external state;
* probabilistic duplicate detection;

but these are outside SPEC-004.

---

## 20. Security / Secrets

No secrets or external services are involved.

---

## 21. Alternatives Considered

### Option A — Return Boolean

```python
validate(bars) -> bool
```

Rejected because it loses diagnostic information.

### Option B — Raise on First Dataset Error

Rejected because a research dataset may contain multiple independent defects.

Collecting structural issues in a report provides more useful diagnostics.

### Option C — Automatically Repair Dataset

Rejected because silent repair can change research inputs and compromise reproducibility.

### Option D — Structured Validation Report

Selected.

Provides:

* human-readable diagnostics;
* machine-readable issue codes;
* summary information;
* future compatibility with CLI and UI reporting.

---

## 22. Dependencies

Depends on:

* SPEC-002 — Canonical Market Bar Model
* SPEC-003 — CSV Market Data Provider for integration testing

Runtime external dependencies:

* none

---

## 23. Implementation Notes

No conflict with the completed SPEC-002 or SPEC-003 implementation was found.

The approved API is implemented in `quantforge.data.validation`. Validation consumes the input
exactly once, compares ordering against the maximum timestamp previously observed for each
symbol, and retains only the state required for summaries, duplicate detection, ordering
detection, and issue reporting. Keeping the maximum prevents one earlier observation from hiding
later observations that remain below the established ordering watermark.

Material deviations from the approved specification must be documented before continuing.

---

## 24. Completion Summary

Status: Completed

Files created:

* `src/quantforge/data/validation.py`
* `tests/test_market_data_validation.py`

Files modified:

* `docs/specs/SPEC-004-market-data-validation.md`
* `docs/specs/INDEX.md`
* `ARCHITECTURE.md`
* `docs/ENGINEERING_LOG.md`

Tests added:

* 25 deterministic tests covering report structure and invariants, empty input, collection and
  one-pass inputs, summaries, duplicate and per-symbol ordering rules, issue ordering, input
  preservation, invalid input, immutability, and direct CSV-provider integration.

Commands run:

* `.venv/bin/python -m pytest` — 128 passed.
* `.venv/bin/python -m ruff check .` — passed.
* `.venv/bin/python -m ruff format --check .` — passed; 11 files already formatted.
* `.venv/bin/python -m mypy src tests` — passed; no issues in 11 source files.
* `git diff --check` — passed.
* Markdown validation — not run because no Markdown validator is configured.

Known limitations:

* Exact duplicate detection retains every unique `(symbol, timestamp)` key and therefore uses
  O(n) memory in the worst case.
* Trading calendars, missing-session detection, frequency inference, corporate actions, price
  anomalies, and data repair remain outside this specification.

Engineering log entries:

* `DECISION-006 — Keep Dataset Validation Diagnostic and Single-Pass`
* `BUG-001 — Cascading Out-of-Order Bars Could Be Missed`

Follow-up specifications:

* None implemented as part of SPEC-004.

Expected next specification:

`SPEC-005 — Parquet Storage Layer`
