# SPEC-002 — Canonical Market Bar Model

Status: Completed
Owner: Paul
Created: 2026-08-31
Updated: 2026-08-31

## 1. Problem

QuantForge will eventually ingest historical market data from multiple sources such as CSV files and external market-data providers.

Different sources may use different:

* field names;
* timestamp conventions;
* numeric types;
* schemas;
* metadata.

Downstream QuantForge systems must not depend on provider-specific representations.

QuantForge therefore needs a small canonical domain model representing one OHLCV market bar.

This model will become the common boundary between market-data ingestion and downstream systems such as:

* validation;
* feature computation;
* backtesting;
* analytics.

---

## 2. Goal

Implement an immutable canonical `Bar` domain object representing one OHLCV observation for one symbol over one time interval.

The implementation must:

* define a stable typed interface;
* validate basic OHLCV invariants;
* reject invalid numeric values;
* require timezone-aware timestamps;
* remain independent of any external data provider;
* remain independent of Pandas, NumPy, DuckDB, Parquet, and trading logic;
* support deterministic equality and hashing.

---

## 3. Non-Goals

SPEC-002 does NOT implement:

* CSV parsing;
* external market-data APIs;
* market-data downloading;
* Parquet persistence;
* DuckDB;
* Pandas or Polars integration;
* adjusted prices;
* corporate actions;
* dividends;
* stock splits;
* symbol-change history;
* trading calendars;
* market sessions;
* returns;
* features;
* strategies;
* portfolio logic;
* orders;
* execution;
* backtesting;
* bid/ask quotes;
* tick-level data.

Those concerns belong to later specifications.

---

## 4. Background

### 4.1 Market Bar

A market bar summarizes trading activity over one time interval.

The standard OHLCV fields are:

* `open`: first relevant traded price in the interval;
* `high`: highest traded price in the interval;
* `low`: lowest traded price in the interval;
* `close`: final relevant traded price in the interval;
* `volume`: total traded quantity in the interval.

Examples of possible intervals include:

* one day;
* one hour;
* one minute.

SPEC-002 defines the canonical observation object only. It does not yet model interval frequency explicitly.

---

## 5. Functional Requirements

### FR-1 — Canonical Type

QuantForge must expose a public immutable `Bar` domain type.

### FR-2 — Required Fields

`Bar` must contain exactly these core fields:

* `symbol`
* `timestamp`
* `open`
* `high`
* `low`
* `close`
* `volume`

No provider-specific metadata belongs in the canonical object.

### FR-3 — Symbol

`symbol` must:

* be a string;
* contain non-whitespace content;
* be normalized by trimming surrounding whitespace;
* be normalized to uppercase.

Examples:

`"aapl"` → `"AAPL"`

`" AAPL "` → `"AAPL"`

Empty or whitespace-only symbols must be rejected.

### FR-4 — Timestamp

`timestamp` must:

* be a `datetime`;
* be timezone-aware;
* reject naive datetimes.

The timestamp represents the start of the bar interval.

QuantForge does not require UTC storage in SPEC-002, but timezone information must always be preserved.

Example:

A future daily U.S. equity bar may use a timestamp corresponding to the start of its trading interval.

Exact exchange-session semantics belong to a later specification.

### FR-5 — Price Representation

The following fields use Python `float`:

* `open`
* `high`
* `low`
* `close`

All prices must be:

* finite;
* strictly greater than zero.

Reject:

* `NaN`;
* positive infinity;
* negative infinity;
* zero;
* negative prices.

### FR-6 — Volume Representation

`volume` must be a Python integer.

It must satisfy:

`volume >= 0`

Zero volume is valid.

Negative volume is invalid.

Boolean values must not be accepted as volume even though Python treats `bool` as a subclass of `int`.

### FR-7 — OHLC Invariants

A valid bar must satisfy:

`high >= open`

`high >= close`

`high >= low`

`low <= open`

`low <= close`

Equivalent canonical checks may be used.

At minimum:

`high >= max(open, close, low)`

and:

`low <= min(open, close, high)`

must hold.

Invalid OHLC combinations must be rejected.

### FR-8 — Immutability

After construction, a `Bar` must not permit mutation of its fields.

Example:

`bar.close = 200`

must fail.

### FR-9 — Equality

Two bars with identical normalized field values must compare equal.

### FR-10 — Hashability

A valid `Bar` must be hashable.

This allows deterministic use in:

* sets;
* dictionaries;
* caches;
* test fixtures.

### FR-11 — Public Import

The canonical public import should be simple.

Preferred target:

```python
from quantforge.domain import Bar
```

or an equally clean domain-level import if the implementation architecture suggests a better location.

Provider-specific modules must not define their own incompatible `Bar` types.

---

## 6. Non-Functional Requirements

### NFR-1 — No External Dependencies

SPEC-002 should use only the Python standard library unless a dependency is already part of SPEC-001 and clearly justified.

Do not add:

* Pandas;
* NumPy;
* Pydantic;
* DuckDB;
* market-data SDKs.

### NFR-2 — Type Safety

All public fields and constructors must use explicit type annotations.

Strict mypy must pass.

### NFR-3 — Determinism

Identical input values must produce identical normalized bar values.

### NFR-4 — Small Domain Surface

The implementation should remain intentionally small.

Do not create speculative abstractions for:

* candles;
* quotes;
* ticks;
* corporate actions;
* frequencies;
* sessions.

### NFR-5 — Clear Failures

Invalid bars must fail immediately at construction rather than entering downstream systems in an invalid state.

---

## 7. Proposed API

Preferred conceptual API:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
```

Validation may be performed in `__post_init__`.

Because the dataclass is frozen, normalized fields such as `symbol` may require careful use of `object.__setattr__` during construction.

Implementation details may differ if they preserve the same public behavior.

---

## 8. Data Model

### `symbol: str`

Canonical uppercase security symbol.

Examples:

* `AAPL`
* `MSFT`
* `SPY`

SPEC-002 does not attempt to support complex global instrument identifiers.

### `timestamp: datetime`

Timezone-aware timestamp representing the start of the bar interval.

### `open: float`

Opening price.

Must be finite and positive.

### `high: float`

Highest price.

Must be finite, positive, and consistent with all other prices.

### `low: float`

Lowest price.

Must be finite, positive, and consistent with all other prices.

### `close: float`

Closing price.

Must be finite and positive.

### `volume: int`

Non-negative traded quantity.

---

## 9. Invariants

Every valid `Bar` must satisfy:

1. `symbol != ""`
2. `symbol == symbol.strip()`
3. `symbol == symbol.upper()`
4. `timestamp.tzinfo is not None`
5. `open > 0`
6. `high > 0`
7. `low > 0`
8. `close > 0`
9. all price fields are finite
10. `volume >= 0`
11. `high >= open`
12. `high >= close`
13. `high >= low`
14. `low <= open`
15. `low <= close`

The object must remain immutable after construction.

---

## 10. Edge Cases

Tests must consider at least:

* lowercase symbol;
* symbol with surrounding whitespace;
* empty symbol;
* whitespace-only symbol;
* naive datetime;
* timezone-aware datetime;
* zero price;
* negative price;
* `NaN`;
* positive infinity;
* negative infinity;
* zero volume;
* negative volume;
* boolean volume;
* `high == low`;
* `open == high`;
* `close == low`;
* `high < open`;
* `high < close`;
* `low > open`;
* `low > close`;
* attempted mutation.

A flat-price bar is valid if:

`open == high == low == close > 0`

---

## 11. Error Handling

Invalid construction should raise `ValueError` for invalid domain values unless Python naturally raises `TypeError` for an incorrect fundamental type.

Error messages should identify the invalid field or violated invariant.

Examples:

* `"symbol must not be empty"`
* `"timestamp must be timezone-aware"`
* `"open must be finite and greater than zero"`
* `"volume must be a non-negative integer"`
* `"high must be greater than or equal to open and close"`

Do not silently coerce fundamentally invalid values.

For example:

* do not convert negative volume to zero;
* do not replace NaN with another price;
* do not invent timezone information for naive timestamps.

---

## 12. Testing Plan

### Unit Tests

Test valid construction with:

* normal OHLCV values;
* lowercase symbol normalization;
* surrounding whitespace normalization;
* zero volume;
* flat-price bar;
* timezone-aware timestamp.

Test invalid construction with:

* empty symbol;
* naive timestamp;
* each non-finite price;
* zero price;
* negative price;
* negative volume;
* boolean volume;
* inconsistent OHLC values.

### Immutability Tests

Verify modifying every public field raises the appropriate frozen-dataclass error or equivalent.

### Equality Tests

Two equivalent bars should compare equal.

Symbol normalization must occur before equality comparison.

Example:

```python
Bar(symbol="aapl", ...)
==
Bar(symbol="AAPL", ...)
```

when all other fields are equal.

### Hash Tests

Equivalent bars should have identical hashes.

The object should work as a dictionary key and set member.

### Regression Tests

None initially.

Any future bug in Bar validation should receive a regression test.

---

## 13. Acceptance Criteria

* [x] `Bar` exists as a public domain object.
* [x] `Bar` contains only the approved seven fields.
* [x] symbols are trimmed and uppercased.
* [x] empty symbols are rejected.
* [x] timestamps must be timezone-aware.
* [x] naive timestamps are rejected.
* [x] all OHLC prices must be finite and positive.
* [x] OHLC consistency is validated.
* [x] volume must be a non-negative integer.
* [x] boolean volume is rejected.
* [x] zero volume is allowed.
* [x] bars are immutable.
* [x] bars are hashable.
* [x] deterministic equality works.
* [x] tests cover all listed edge cases.
* [x] no external runtime dependency is introduced.
* [x] Ruff passes.
* [x] formatting checks pass.
* [x] strict mypy passes.
* [x] pytest passes.
* [x] `docs/specs/INDEX.md` is updated.
* [x] architecture documentation is updated only if needed.
* [x] meaningful implementation decisions are recorded in the engineering log.

---

## 14. Performance Considerations

Performance is not a primary concern in SPEC-002.

However, market-data workloads may eventually contain millions of bars.

The implementation should avoid obviously unnecessary object overhead.

A frozen dataclass with `slots=True` is preferred if it remains clear and correct.

No performance claim should be made without benchmarking.

---

## 15. Security / Secrets

No credentials or external services are involved.

---

## 16. Alternatives Considered

### Option A — Plain Dictionary

Example:

```python
{
    "symbol": "AAPL",
    "open": 100.0,
    ...
}
```

Advantages:

* simple;
* flexible.

Disadvantages:

* weak type safety;
* mutation-prone;
* easy to omit fields;
* unclear invariants;
* poor domain boundary.

Rejected.

### Option B — Pydantic Model

Advantages:

* strong validation utilities;
* serialization support.

Disadvantages:

* introduces a dependency for a very small core domain object;
* validation behavior may be more permissive than desired;
* unnecessary at this stage.

Rejected for SPEC-002.

### Option C — Frozen Standard-Library Dataclass

Advantages:

* no dependency;
* immutable;
* type-friendly;
* explicit;
* hashable;
* supports `slots`.

Disadvantages:

* validation must be written manually.

Selected.

---

## 17. Dependencies

Depends on:

* SPEC-001 — Repository Foundation

External dependencies:

* none

---

## 18. Implementation Notes

No conflict was found between this specification and the existing SPEC-001 repository foundation. The approved scope was implemented without deviation.

`Bar` lives in the single `quantforge.domain` module because SPEC-002 introduces only one domain type. A package hierarchy would add structure without a current requirement.

Construction explicitly raises `TypeError` for incorrect fundamental runtime types and `ValueError` for invalid domain values. Timezone-aware timestamps are preserved rather than converted to UTC.

Any material deviation from this specification must be documented before completion.

---

## 19. Completion Summary

Status: Completed

Files created:

* `docs/specs/SPEC-002-market-bar-model.md`
* `src/quantforge/domain.py`
* `tests/test_bar.py`

Files modified:

* `ARCHITECTURE.md`
* `docs/ENGINEERING_LOG.md`
* `docs/specs/INDEX.md`

Tests added:

* 59 deterministic `Bar` test cases covering the public fields, construction, normalization, types, domain invariants, boundary equality, immutability, equality, hashing, dictionary keys, and set membership.

Commands run:

* `python -m pytest` — 63 passed.
* `python -m ruff check .` — passed.
* `python -m ruff format --check .` — passed.
* `python -m mypy src tests` — passed in strict mode.

Known limitations:

* Bar frequency and exchange-session semantics are not modeled.
* Timestamps retain their supplied timezone and are not normalized to UTC.
* Prices use Python `float` as approved by this specification.
* Serialization, adjusted prices, corporate actions, and provider integrations are not implemented.

Follow-up specifications:

* SPEC-003 may define CSV ingestion that constructs canonical `Bar` objects.

Expected next specification:

`SPEC-003 — CSV Market Data Provider`

Related engineering-log entries:

* `DECISION-004 — Represent Canonical Market Bars with a Frozen Slotted Dataclass`
