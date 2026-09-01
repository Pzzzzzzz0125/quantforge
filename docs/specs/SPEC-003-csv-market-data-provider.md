# SPEC-003 — CSV Market Data Provider

Status: Completed
Owner: Paul
Created: 2026-08-31
Updated: 2026-09-01

## 1. Problem

QuantForge now has a canonical `Bar` domain model, but no mechanism exists for loading historical market data from external files.

Research and testing need a deterministic, network-independent data source before external market-data APIs are introduced.

CSV is the simplest initial ingestion boundary.

QuantForge therefore needs a CSV market-data provider that converts canonical CSV rows into validated `Bar` objects without leaking CSV-specific representation into downstream systems.

---

## 2. Goal

Implement a small, deterministic CSV market-data provider that:

* reads a canonical OHLCV CSV file;
* parses textual values into approved Python domain types;
* constructs canonical `Bar` instances;
* yields bars incrementally rather than loading the entire file into memory;
* provides useful row-level errors;
* remains independent of Pandas and other external data libraries.

The provider is responsible for parsing.

The `Bar` domain model remains responsible for bar-level domain validation.

---

## 3. Non-Goals

SPEC-003 does NOT implement:

* external market-data APIs;
* HTTP requests;
* provider authentication;
* Pandas;
* NumPy;
* Polars;
* Parquet;
* DuckDB;
* dataset versioning;
* data caching;
* duplicate detection;
* timestamp sorting;
* missing-date detection;
* exchange calendars;
* market-session validation;
* corporate actions;
* price adjustment;
* symbol-history management;
* feature computation;
* strategies;
* backtesting;
* portfolio logic.

Cross-row and dataset-level validation belongs to SPEC-004.

---

## 4. Background

### 4.1 Canonical Boundary

SPEC-002 introduced:

```python
from quantforge.domain import Bar
```

A CSV provider converts an external representation:

```csv
symbol,timestamp,open,high,low,close,volume
AAPL,2026-08-31T09:30:00-04:00,100.0,105.0,99.0,103.0,1000000
```

into:

```python
Bar(
    symbol="AAPL",
    timestamp=...,
    open=100.0,
    high=105.0,
    low=99.0,
    close=103.0,
    volume=1_000_000,
)
```

Downstream systems should receive `Bar` objects rather than raw CSV dictionaries.

### 4.2 Provider Responsibility

The CSV provider owns:

* file reading;
* header validation;
* textual parsing;
* row context;
* conversion to canonical Python types.

The `Bar` model owns:

* symbol normalization;
* timezone-awareness validation;
* finite positive price validation;
* OHLC consistency;
* volume-domain validation.

This separation avoids duplicating domain rules.

---

## 5. Canonical CSV Schema

The initial CSV schema requires the following columns:

* `symbol`
* `timestamp`
* `open`
* `high`
* `low`
* `close`
* `volume`

Example:

```csv
symbol,timestamp,open,high,low,close,volume
AAPL,2026-08-31T09:30:00-04:00,100.0,105.0,99.0,103.0,1000000
MSFT,2026-08-31T09:30:00-04:00,200.0,206.0,198.0,204.0,750000
```

Column names are canonical and lowercase.

Header names may have surrounding whitespace trimmed before validation.

SPEC-003 does not implement arbitrary provider-specific column mappings.

Extra columns may be present but are ignored.

Missing required columns must cause failure before rows are yielded.

---

## 6. Functional Requirements

### FR-1 — Public Provider

QuantForge must expose a CSV market-data provider.

Preferred conceptual API:

```python
from quantforge.data.csv import CSVMarketDataProvider
```

Example:

```python
provider = CSVMarketDataProvider("data/sample/bars.csv")

for bar in provider.iter_bars():
    ...
```

A similarly clean package structure is acceptable if consistent with the existing architecture.

---

### FR-2 — Path Input

The provider must accept:

```python
str | pathlib.Path
```

The path is stored internally as a `Path`.

No file should be read during construction unless necessary.

Actual reading should occur when iteration begins.

---

### FR-3 — Streaming Iteration

The provider must expose:

```python
iter_bars() -> Iterator[Bar]
```

Bars should be produced incrementally.

Do not load the entire CSV into a list before yielding results.

This preserves a future path toward large datasets.

---

### FR-4 — Required Headers

Before yielding data, the provider must verify that all canonical columns exist:

* symbol
* timestamp
* open
* high
* low
* close
* volume

Missing required columns must raise `ValueError`.

The error message must identify the missing column or columns.

---

### FR-5 — Header Normalization

Surrounding whitespace around header names may be removed.

For example:

```text
" symbol "
```

may be interpreted as:

```text
"symbol"
```

Header-name case conversion is NOT required.

The canonical schema remains lowercase.

---

### FR-6 — Extra Columns

Extra CSV columns are permitted.

They must not be added to `Bar`.

They are ignored by SPEC-003.

---

### FR-7 — Symbol Parsing

The provider should pass the textual symbol to `Bar`.

`Bar` remains responsible for:

* trimming value whitespace;
* uppercasing;
* rejecting empty symbols.

The provider must not create an independent symbol-normalization rule.

---

### FR-8 — Timestamp Parsing

Timestamp values must be parsed using ISO-8601-compatible semantics supported by the Python standard library.

Preferred implementation:

```python
datetime.fromisoformat(...)
```

Examples of valid representations include:

```text
2026-08-31T09:30:00-04:00
2026-08-31T13:30:00+00:00
```

Naive timestamps may parse successfully but will subsequently be rejected by `Bar`.

The provider must not invent timezone information.

---

### FR-9 — Price Parsing

The textual fields:

* open
* high
* low
* close

must be parsed explicitly into Python `float`.

Example:

```text
"100.25"
```

becomes:

```python
100.25
```

The provider must not perform additional domain correction.

For example, it must not:

* replace NaN;
* clamp negative values;
* reorder high and low.

Invalid domain values must be rejected by `Bar`.

---

### FR-10 — Volume Parsing

Volume must be parsed into Python `int`.

Examples:

```text
"1000000"
```

→

```python
1_000_000
```

Non-integral representations such as:

```text
"100.5"
```

must fail.

The provider must not round volume.

---

### FR-11 — Row-Level Construction

Each successfully parsed row must construct exactly one canonical `Bar`.

The provider must yield the constructed `Bar`.

---

### FR-12 — Row Order

The provider must preserve CSV row order.

SPEC-003 must not sort data.

---

### FR-13 — No Deduplication

Duplicate rows or duplicate symbol/timestamp combinations must not be silently removed.

Dataset-level duplicate detection belongs to SPEC-004.

---

### FR-14 — Header-Only File

A valid CSV containing only the required header and no rows is valid.

`iter_bars()` should yield zero bars.

---

### FR-15 — Empty File

A completely empty CSV has no valid schema.

It must fail clearly because required headers are unavailable.

---

### FR-16 — UTF-8 Input

CSV files should be read as UTF-8.

Using `utf-8-sig` is acceptable and preferred if it cleanly supports UTF-8 files containing a BOM.

---

## 7. Non-Functional Requirements

### NFR-1 — No New Runtime Dependency

Use the Python standard library.

Do not introduce:

* Pandas;
* Polars;
* NumPy;
* Pydantic.

### NFR-2 — Determinism

Identical CSV bytes must produce identical `Bar` sequences.

### NFR-3 — Streaming

Memory consumption should not grow linearly merely because the provider stores all parsed bars.

### NFR-4 — Testability

All behavior must be testable using temporary local files.

No network access is permitted.

### NFR-5 — Type Safety

Public interfaces must contain explicit type annotations.

Strict mypy must pass.

### NFR-6 — Error Context

Parsing failures should identify enough context to locate the invalid row.

At minimum, errors caused by row contents should include the CSV line number.

---

## 8. Proposed API

Preferred conceptual API:

```python
from pathlib import Path
from collections.abc import Iterator

from quantforge.domain import Bar


class CSVMarketDataProvider:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def iter_bars(self) -> Iterator[Bar]:
        ...
```

A generic cross-provider protocol is intentionally NOT introduced in SPEC-003.

The requirements for network providers are not yet understood well enough to freeze such an interface.

A future specification may extract a common provider protocol once at least two concrete provider implementations exist.

---

## 9. Data Model

No new financial domain model is introduced.

The provider outputs:

```python
Bar
```

defined by SPEC-002.

Provider state may include:

```text
path
```

but must not be embedded into the resulting `Bar`.

---

## 10. Parsing Boundary

Parsing proceeds conceptually as:

```text
CSV bytes
    ↓
text rows
    ↓
dictionary by header
    ↓
type conversion
    ↓
Bar(...)
    ↓
canonical validated domain object
```

The CSV layer validates syntax and structural requirements.

The `Bar` layer validates financial/domain invariants.

---

## 11. Invariants

For every yielded value:

```python
isinstance(value, Bar)
```

must be true.

The provider must:

* preserve input row order;
* yield at most one `Bar` per data row;
* never silently discard malformed rows;
* never silently repair invalid domain data;
* never modify provider provenance into the `Bar`.

---

## 12. Error Handling

### File Errors

Natural filesystem exceptions should generally propagate.

Examples:

* `FileNotFoundError`
* `PermissionError`
* `IsADirectoryError`

Do not convert all filesystem errors into generic `ValueError`.

### Missing Headers

Raise `ValueError`.

The message must identify missing canonical fields.

### Timestamp Parse Failure

Raise an error containing:

* row/line number;
* timestamp context.

The original parsing exception should preferably be preserved as the cause.

### Price Parse Failure

Raise an error containing:

* row/line number;
* affected field.

### Volume Parse Failure

Raise an error containing:

* row/line number;
* volume context.

### Bar Domain Failure

If `Bar(...)` raises `TypeError` or `ValueError`, add CSV row context while preserving the underlying cause.

Do not silently skip the row.

---

## 13. Edge Cases

Tests must cover at least:

* normal one-row CSV;
* multiple symbols;
* multiple rows;
* preserved row order;
* lowercase symbol passed through and normalized by `Bar`;
* whitespace around symbol value;
* timezone-aware timestamp;
* naive timestamp rejected through `Bar`;
* malformed timestamp;
* positive prices;
* zero price;
* negative price;
* NaN price;
* infinite price;
* valid integer volume;
* zero volume;
* negative volume;
* decimal volume;
* empty volume;
* invalid OHLC relationship;
* missing each required header;
* several missing headers;
* extra header;
* extra ignored values;
* surrounding header whitespace;
* header-only file;
* completely empty file;
* missing file;
* UTF-8 BOM where supported;
* duplicate rows preserved;
* out-of-order timestamps preserved.

---

## 14. Testing Plan

### Unit Tests

Use pytest `tmp_path` to construct deterministic local CSV files.

Test:

* parsing;
* header handling;
* conversions;
* row ordering;
* edge cases;
* errors.

### Integration Test

Create a small canonical CSV containing multiple symbols.

Read it through the provider.

Verify the exact expected sequence of `Bar` objects.

### Boundary Tests

Ensure domain errors originate from `Bar` rules rather than duplicated CSV-specific financial validation.

### Network

No network tests.

---

## 15. Acceptance Criteria

* [x] `CSVMarketDataProvider` exists.
* [x] The provider accepts `str | Path`.
* [x] The provider exposes streaming `iter_bars()`.
* [x] Required canonical headers are validated.
* [x] Header whitespace is handled as specified.
* [x] Extra columns are ignored.
* [x] ISO timestamps are parsed with standard-library behavior.
* [x] No timezone is invented.
* [x] prices are converted to `float`.
* [x] volume is converted to `int` without rounding.
* [x] canonical `Bar` objects are produced.
* [x] row order is preserved.
* [x] duplicate rows are preserved.
* [x] out-of-order timestamps are preserved.
* [x] header-only files produce zero bars.
* [x] completely empty files fail clearly.
* [x] filesystem errors remain meaningful.
* [x] malformed row errors contain line context.
* [x] invalid domain values are not silently repaired.
* [x] no new runtime dependency is introduced.
* [x] tests are deterministic and network-independent.
* [x] Ruff passes.
* [x] formatting passes.
* [x] strict mypy passes.
* [x] pytest passes.
* [x] `git diff --check` passes.
* [x] SPEC index is updated.
* [x] architecture documentation is updated only if appropriate.
* [x] meaningful decisions or bugs are logged.

---

## 16. Performance Considerations

SPEC-003 does not require performance optimization.

However, the interface intentionally streams bars so that future large CSV datasets do not require loading the entire dataset into memory.

No throughput claim should be made without benchmarking.

---

## 17. Security / Secrets

No credentials are used.

The implementation must not execute or evaluate CSV content as code.

---

## 18. Alternatives Considered

### Option A — Pandas `read_csv`

Advantages:

* convenient;
* fast;
* familiar.

Disadvantages:

* introduces a major dependency;
* obscures the basic ingestion boundary;
* tends to load whole datasets;
* unnecessary for the first provider.

Rejected for SPEC-003.

### Option B — Return Raw Dictionaries

Advantages:

* simple.

Disadvantages:

* leaks external representation;
* weak typing;
* bypasses canonical domain validation.

Rejected.

### Option C — Standard-Library Streaming CSV Provider

Advantages:

* no dependency;
* deterministic;
* explicit;
* easy to test;
* naturally streaming;
* exercises the canonical `Bar` boundary.

Selected.

### Option D — Define Generic `MarketDataProvider` Protocol Now

Advantages:

* immediate abstraction across future providers.

Disadvantages:

* only one concrete provider currently exists;
* API requirements for historical network providers have not yet been designed;
* risks premature abstraction.

Deferred.

---

## 19. Dependencies

Depends on:

* SPEC-001 — Repository Foundation
* SPEC-002 — Canonical Market Bar Model

External runtime dependencies:

* none

---

## 20. Implementation Notes

No conflict was found between this specification, the existing repository foundation, and the completed SPEC-002 `Bar` implementation. The approved scope was implemented without deviation.

The provider uses `csv.reader` rather than `csv.DictReader` so blank physical rows can be treated as malformed rows instead of being silently skipped. Canonical header positions are resolved once before any bar is yielded.

Parsing helpers perform only structural checks and textual conversion. `Bar` remains the sole owner of symbol normalization, timezone awareness, finite positive prices, non-negative volume, and OHLC consistency.

Filesystem exceptions propagate naturally. CSV syntax, conversion, and domain failures add physical CSV line context and preserve their underlying exception through chaining.

Material deviations must be documented before completion.

---

## 21. Completion Summary

Status: Completed

Files created:

* `docs/specs/SPEC-003-csv-market-data-provider.md`
* `src/quantforge/data/__init__.py`
* `src/quantforge/data/csv.py`
* `tests/test_csv_market_data_provider.py`

Files modified:

* `ARCHITECTURE.md`
* `docs/ENGINEERING_LOG.md`
* `docs/specs/INDEX.md`

Tests added:

* 39 deterministic temporary-file cases covering path types, lazy streaming, exact integration output, headers, UTF-8 BOM input, row order, duplicates, timestamps, numeric conversion, delegated domain failures, filesystem errors, malformed/blank/short rows, line context, and exception causes.

Commands run:

* `python -m pytest` — 103 passed.
* `python -m ruff check .` — passed.
* `python -m ruff format --check .` — passed.
* `python -m mypy src tests` — passed in strict mode.
* Relative Markdown-link validation — passed.
* `git diff --check` — passed.

Known limitations:

* Only canonical lowercase headers are supported; arbitrary column mappings are not implemented.
* Cross-row validation, sorting, deduplication, missing-date checks, and data repair are not implemented.
* Timestamp parsing follows `datetime.fromisoformat`; timezone information is required by `Bar` but is not invented or normalized.
* Only local UTF-8 CSV files are supported.

Engineering log entries:

* `DECISION-005 — Keep CSV Parsing Separate from Bar Domain Validation`

Follow-up specifications:

* SPEC-004 may validate sequences of canonical bars for cross-row and dataset-level issues.

Expected next specification:

`SPEC-004 — Market Data Validation`
