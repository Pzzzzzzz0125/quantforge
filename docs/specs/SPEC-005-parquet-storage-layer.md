# SPEC-005 — Parquet Storage Layer

Status: Completed
Owner: Paul
Created: 2026-09-01
Updated: 2026-09-01

## 1. Problem

QuantForge can ingest canonical CSV market data and validate dataset-level structural relationships, but it does not yet have an efficient persistent storage format for research datasets.

CSV is useful as an ingestion and interchange format, but it has several limitations for repeated quantitative research:

* values must be reparsed from text;
* schema typing is weak;
* files are relatively large;
* selective analytical reads are inefficient;
* timestamp semantics are not encoded strongly;
* downstream analytical engines cannot exploit columnar storage.

QuantForge therefore needs a canonical Parquet storage layer for persisted market bars.

---

## 2. Goal

Implement a deterministic local Parquet storage layer that:

* writes canonical `Bar` objects to Parquet;
* reads Parquet files back into canonical `Bar` objects;
* uses an explicit, versioned storage schema;
* stores timestamps as timezone-aware UTC timestamps;
* preserves row order;
* supports one-pass iterable inputs;
* avoids loading an entire dataset into memory merely for convenience;
* uses atomic replacement so failed writes do not leave a partially written destination file;
* introduces PyArrow as the first justified runtime data dependency.

The storage layer performs serialization and schema enforcement.

It does not perform dataset-quality validation, sorting, deduplication, or repair.

---

## 3. Non-Goals

SPEC-005 does NOT implement:

* DuckDB;
* dataset cataloging;
* dataset IDs;
* dataset manifests;
* partitioned datasets;
* symbol/date directory partitioning;
* remote/object storage;
* S3;
* cloud storage;
* external market-data APIs;
* automatic market-data validation;
* sorting;
* deduplication;
* missing-session detection;
* trading calendars;
* corporate actions;
* feature storage;
* experiment tracking;
* strategies;
* backtesting;
* caching;
* database indexing;
* arbitrary Parquet schemas;
* Pandas;
* Polars.

Dataset cataloging belongs to SPEC-006.

---

## 4. Background

### 4.1 Why Parquet

Parquet is a typed columnar storage format.

Instead of repeatedly storing textual values such as:

```text
"AAPL","2026-08-31T09:30:00-04:00","100.25"
```

Parquet stores typed columns such as:

```text
symbol      string
timestamp   timestamp
open        float64
...
```

This is better suited to analytical research workloads.

### 4.2 Storage Boundary

QuantForge's financial domain remains:

```python
from quantforge.domain import Bar
```

Parquet is a persistence representation.

Downstream research logic should operate on domain objects or future analytical interfaces rather than depending directly on PyArrow-specific objects unless another specification explicitly introduces such an interface.

---

## 5. Dependency Decision

SPEC-005 introduces:

```text
PyArrow
```

as a runtime dependency.

PyArrow is justified because QuantForge now requires native Parquet serialization and reading.

Do not introduce Pandas merely to access Parquet.

The implementation should use PyArrow directly.

Dependency metadata must be updated through the project's normal package configuration.

The implementation must remain compatible with the project's supported Python version.

---

## 6. Canonical Parquet Schema

Version 1 contains exactly these financial fields:

```text
symbol
timestamp
open
high
low
close
volume
```

Preferred logical types:

```text
symbol      string
timestamp   timestamp[us, UTC]
open        float64
high        float64
low         float64
close       float64
volume      int64
```

The exact PyArrow schema should be defined once and reused for both reads and writes.

Do not infer the canonical schema independently on every write.

---

## 7. Timestamp Policy

Canonical `Bar` objects require timezone-aware timestamps.

For persistence, every timestamp must be normalized to UTC before storage.

Example:

```text
2026-08-31 09:30:00-04:00
```

and:

```text
2026-08-31 13:30:00+00:00
```

represent the same instant.

The stored Parquet timestamp should represent:

```text
2026-08-31 13:30:00+00:00
```

Round-trip semantics guarantee preservation of the same instant.

They do NOT guarantee preservation of the original timezone representation or UTC offset.

When read back, timestamps should be UTC-aware.

This is an intentional canonical storage normalization.

The storage layer must never interpret a naive timestamp because canonical `Bar` objects already reject naive timestamps.

---

## 8. Schema Version

Parquet files written by QuantForge should contain storage-format metadata identifying the schema version.

Preferred conceptual metadata:

```text
quantforge_schema_version = 1
```

An implementation may also include a format identifier such as:

```text
quantforge_format = market_bars
```

if useful.

Do not introduce a complex metadata framework.

The version must be defined centrally rather than duplicated across functions.

---

## 9. Public API

Preferred API:

```python
from quantforge.data.parquet import ParquetMarketDataStore

store = ParquetMarketDataStore("data/processed/bars.parquet")

count = store.write_bars(bars)

for bar in store.iter_bars():
    ...
```

Constructor:

```python
ParquetMarketDataStore(path: str | Path)
```

Writer:

```python
write_bars(
    bars: Iterable[Bar],
    *,
    overwrite: bool = False,
) -> int
```

Reader:

```python
iter_bars() -> Iterator[Bar]
```

A similarly small API is acceptable if strongly justified.

Do not introduce a generic storage protocol in SPEC-005.

There is currently only one persistent storage implementation.

---

## 10. Path Behavior

The constructor accepts:

```python
str | Path
```

and stores a `Path` internally.

Construction should not immediately access the filesystem.

Filesystem interaction occurs during reads or writes.

The implementation should not silently create an arbitrary missing directory tree.

The destination parent directory must already exist.

Natural filesystem errors should remain meaningful.

---

## 11. Write Behavior

### 11.1 Iterable Input

`write_bars` must accept:

```python
Iterable[Bar]
```

including one-pass generators.

### 11.2 Type Contract

Every item must be a canonical `Bar`.

A non-`Bar` value must raise a clear `TypeError` identifying its position when practical.

### 11.3 Preserve Order

Rows must be stored in encounter order.

The writer must not:

* sort;
* deduplicate;
* group by symbol;
* repair input.

### 11.4 One-Pass Consumption

The writer should consume the input iterable once.

Do not call:

```python
list(bars)
```

solely for convenience.

### 11.5 Batching

Writing may use bounded internal batches.

The implementation should avoid retaining the entire iterable in memory.

A reasonable internal batch size may be selected and documented.

The batch size does not need to become part of the public API in SPEC-005.

### 11.6 Return Value

`write_bars` returns the number of bars successfully written.

For an empty iterable:

```python
0
```

is returned.

---

## 12. Atomic Write Semantics

Writes must not expose partially written destination files.

The preferred behavior is:

```text
write temporary file in destination directory
        ↓
finish and close successfully
        ↓
atomically replace/move into target path
```

If writing fails:

* the temporary file should be cleaned up where practical;
* an existing destination must remain unchanged;
* a new destination must not remain as a corrupt partial Parquet file.

Use standard filesystem primitives where possible.

Do not invent a transaction framework.

---

## 13. Overwrite Policy

Default behavior:

```python
overwrite=False
```

If the destination already exists, writing must fail clearly rather than silently replacing research data.

If:

```python
overwrite=True
```

the completed temporary file may atomically replace the existing destination.

This explicit policy supports reproducibility and prevents accidental dataset destruction.

---

## 14. Empty Dataset

Writing an empty iterable is valid.

The result must be a valid Parquet file containing:

* the canonical schema;
* zero rows;
* supported QuantForge schema metadata.

Reading that file yields zero `Bar` objects.

This behavior allows pipelines to represent an intentionally empty result without inventing a special file format.

---

## 15. Price Storage

The canonical:

```text
open
high
low
close
```

fields are stored as `float64`.

No price rounding or transformation is permitted.

The storage layer relies on the canonical `Bar` domain rules for financial validity.

---

## 16. Volume Storage

Volume is stored as signed `int64`.

Canonical `Bar.volume` is a Python integer and therefore may theoretically exceed the storage range.

If a valid Python integer cannot be represented as signed `int64`, the writer must fail clearly.

It must not:

* wrap;
* truncate;
* convert to floating point;
* silently saturate the value.

The error should contain row context where practical.

---

## 17. Reading

`iter_bars()` must:

* open the Parquet file lazily when iteration begins;
* inspect and validate the storage schema;
* read data incrementally using batches or row groups;
* yield canonical `Bar` instances;
* preserve persisted row order.

The reader must not load the entire Parquet dataset merely for convenience.

---

## 18. Schema Validation on Read

Before yielding rows, the reader must verify that the file is compatible with the canonical QuantForge market-bar storage format.

Validation should include at minimum:

* required canonical field names;
* compatible canonical field types;
* UTC timezone-aware timestamp storage;
* supported schema version metadata.

An unsupported QuantForge schema version must fail clearly.

A malformed or incompatible Parquet schema must not be silently coerced into the canonical domain.

---

## 19. Domain Reconstruction

Each persisted record should reconstruct:

```python
Bar(...)
```

The existing `Bar` constructor remains the final domain boundary.

Do not bypass domain construction by returning raw Arrow rows.

If persisted contents somehow violate `Bar` invariants, reading must fail rather than silently repair them.

---

## 20. Dataset Validation Separation

SPEC-005 does not automatically call:

```python
MarketDataValidator
```

before or after persistence.

Therefore a dataset containing valid individual bars but duplicate or out-of-order observations may still be persisted.

This is intentional.

The caller explicitly chooses when dataset validation is required.

The storage layer must preserve such rows exactly in encounter order.

---

## 21. Compression

Parquet output should use an appropriate standard compression codec.

`zstd` is preferred if available through the selected PyArrow installation.

Compression is an implementation-level storage choice and must not alter domain semantics.

Do not expose compression tuning as a public configuration surface in SPEC-005.

---

## 22. Determinism

Given the same ordered sequence of canonical bars, reading the resulting dataset must produce the same ordered sequence of market observations, modulo the documented conversion of timestamps to UTC.

Byte-for-byte identical Parquet output is NOT required.

Parquet metadata or library versions may prevent byte-identical files.

Semantic determinism is required.

---

## 23. Error Handling

### Filesystem Errors

Meaningful filesystem errors should propagate where appropriate, including:

* `FileNotFoundError`;
* `PermissionError`;
* directory/path-related errors.

### Existing Destination

Attempting to write to an existing destination with:

```python
overwrite=False
```

must fail clearly.

### Input Type Error

A non-`Bar` item must raise `TypeError`.

### Storage Range Failure

Values that cannot fit the canonical storage type must fail clearly.

### Incompatible Schema

An incompatible Parquet file must fail clearly before yielding misleading domain values.

### Unsupported Version

Unsupported QuantForge Parquet schema metadata must fail clearly.

### Corrupt Parquet

Corrupt or unreadable Parquet contents should produce a stable, understandable failure while preserving the original PyArrow exception as the cause where practical.

Do not catch unrelated programming exceptions broadly.

---

## 24. Public Dependency Leakage

PyArrow is an implementation dependency of this storage layer.

The preferred public API should expose:

```text
Bar
Iterator[Bar]
int
Path-like inputs
standard Python exceptions / stable QuantForge errors if justified
```

rather than requiring callers to manipulate:

```text
pyarrow.Table
pyarrow.RecordBatch
pyarrow.Schema
```

Public Arrow-native analytical APIs may be considered later if profiling shows they are valuable.

---

## 25. Internal Architecture

A straightforward design may contain:

```text
ParquetMarketDataStore
canonical Arrow schema
schema-version constants
Bar → Arrow conversion helpers
Arrow → Bar conversion helpers
bounded batch writer
schema compatibility validator
```

Do not create unnecessary repository/service/factory abstractions.

---

## 26. Invariants

Every successfully read item must satisfy:

```python
isinstance(bar, Bar)
```

For a successful round trip:

```text
symbol preserved
OHLC preserved
volume preserved
timestamp instant preserved
row order preserved
row count preserved
```

Original timezone presentation is not required to be preserved because persistent timestamps are normalized to UTC.

The writer must never silently:

* lose rows;
* add rows;
* reorder rows;
* deduplicate rows;
* modify prices;
* modify volume.

---

## 27. Edge Cases

Tests must cover at least:

* one bar;
* multiple bars;
* multiple symbols;
* list input;
* tuple input;
* one-shot generator input;
* bounded/streamed writing behavior;
* lazy reading;
* row order preservation;
* duplicate rows preserved;
* out-of-order rows preserved;
* empty iterable;
* empty Parquet round trip;
* timezone offset converted to equivalent UTC instant;
* already-UTC timestamp;
* OHLC values preserved;
* zero volume;
* large valid int64 volume;
* volume beyond int64 range;
* non-`Bar` item;
* nonexistent read path;
* missing parent directory on write;
* existing destination with overwrite disabled;
* explicit overwrite;
* failed write does not destroy existing destination;
* canonical schema fields;
* canonical schema types;
* schema metadata/version;
* unsupported schema version;
* incompatible timestamp type;
* incompatible column type;
* corrupt Parquet file;
* round-trip integration from CSV provider;
* round-trip of a dataset containing duplicate observations;
* domain reconstruction through `Bar`.

---

## 28. Testing Strategy

Use deterministic local temporary files.

No network access is permitted.

### Unit Tests

Test:

* path handling;
* write counts;
* overwrite policy;
* canonical schema;
* metadata;
* type conversion;
* timestamp normalization;
* invalid input;
* empty input;
* atomic failure behavior.

### Round-Trip Tests

Construct canonical bars:

```text
Bar → Parquet → Bar
```

and verify semantic equality after expected UTC timestamp normalization.

### CSV Integration Test

Use:

```python
CSVMarketDataProvider(...).iter_bars()
```

directly as the writer input.

Then read the Parquet output and verify the expected bars.

This confirms that one-pass ingestion can flow directly into persistent storage.

### Dataset Validation Separation Test

Persist bars containing a duplicate or out-of-order relationship.

Verify storage preserves them.

Optionally feed the read iterator into:

```python
MarketDataValidator().validate(...)
```

and verify SPEC-004 can still diagnose the preserved defect.

---

## 29. Acceptance Criteria

* [x] PyArrow is introduced as a justified runtime dependency.
* [x] No Pandas or Polars dependency is introduced.
* [x] A canonical Parquet market-bar schema exists.
* [x] Schema definition is centralized.
* [x] Storage schema has an explicit version.
* [x] QuantForge schema metadata is written.
* [x] `ParquetMarketDataStore` or equivalent small public API exists.
* [x] Constructor accepts `str | Path`.
* [x] Filesystem access is deferred until read/write operations.
* [x] Writer accepts `Iterable[Bar]`.
* [x] One-shot generator input is supported.
* [x] Writer does not materialize the entire iterable merely for convenience.
* [x] Internal bounded batching is used.
* [x] `write_bars` returns the number of rows written.
* [x] Row order is preserved.
* [x] Duplicates are preserved.
* [x] Out-of-order rows are preserved.
* [x] No dataset repair or validation is performed automatically.
* [x] Timestamps are stored as UTC-aware typed timestamps.
* [x] Timestamp instant is preserved across round trip.
* [x] Original timezone representation is not falsely promised.
* [x] Prices are stored as float64.
* [x] Volume is stored as int64.
* [x] Out-of-range volume fails without coercion.
* [x] Empty iterable creates a valid zero-row Parquet file.
* [x] Reader yields `Iterator[Bar]`.
* [x] Reader operates incrementally.
* [x] Reader validates schema compatibility.
* [x] Reader validates supported schema version.
* [x] Domain objects are reconstructed through `Bar`.
* [x] Existing destination is protected by default.
* [x] Explicit overwrite is supported.
* [x] Writes use atomic destination replacement.
* [x] Failed writes do not leave a corrupt destination.
* [x] Filesystem errors remain meaningful.
* [x] Corrupt/incompatible Parquet input fails clearly.
* [x] CSV-to-Parquet integration is tested.
* [x] Parquet-to-validator integration is tested.
* [x] Tests are deterministic and network-independent.
* [x] pytest passes.
* [x] Ruff lint passes.
* [x] Ruff formatting passes.
* [x] strict mypy passes.
* [x] `git diff --check` passes.
* [x] specification index is updated.
* [x] architecture documentation is updated only for implemented architecture.
* [x] meaningful dependency/storage decisions are recorded.

---

## 30. Performance Considerations

Parquet exists partly to improve analytical storage efficiency, but SPEC-005 does not make unmeasured performance claims.

Expected writer complexity is approximately:

```text
Time: O(n)
```

for `n` bars.

Memory should be bounded primarily by the selected write batch size rather than total dataset size.

Reader memory should similarly depend primarily on Arrow batch/row-group size rather than total file size.

Performance benchmarking belongs to later specifications.

---

## 31. Security / Secrets

No credentials or network services are involved.

Input Parquet files are data and must never be executed as code.

Temporary files should be created safely in the destination filesystem.

---

## 32. Alternatives Considered

### CSV as Primary Research Storage

Rejected.

CSV remains useful for ingestion, but repeated parsing and weak typing make it a poor primary analytical storage format.

### Pandas + Parquet

Rejected for SPEC-005.

Parquet does not justify introducing both Pandas and PyArrow when PyArrow can implement the storage boundary directly.

### Pickle

Rejected.

Pickle is Python-specific, unsafe for untrusted data, and poor for analytical interoperability.

### SQLite

Not selected for canonical bar storage.

Useful for relational metadata, but less suitable than Parquet for large columnar historical market datasets.

### PyArrow + Canonical Parquet Schema

Selected.

It provides:

* strong typing;
* compression;
* columnar storage;
* interoperability;
* future DuckDB compatibility;
* batch-oriented reads and writes.

---

## 33. Dependencies

Depends on:

* SPEC-002 — Canonical Market Bar Model
* SPEC-003 — CSV Market Data Provider
* SPEC-004 — Market Data Validation

New runtime dependency:

```text
PyArrow
```

SPEC-006 may build dataset cataloging on top of the storage layer.

---

## 34. Engineering Decision Expected

Record a meaningful decision describing why QuantForge selected:

```text
PyArrow + canonical versioned Parquet schema + UTC persistence
```

instead of CSV-only or Pandas-backed persistence.

Use the next available `DECISION-XXX` identifier.

---

## 35. Implementation Notes

No conflict with the completed SPEC-002, SPEC-003, or SPEC-004 implementation was found.

The canonical version-1 Arrow schema uses seven non-null fields with the approved logical types
and `quantforge_schema_version = 1` schema metadata. PyArrow 25.0.1 was selected because it is the
current Apache release and publishes Python 3.12 wheels for the project's supported platform
families.

Writes retain at most 1,024 `Bar` references per internal batch, normalize timestamps with
`astimezone(UTC)`, write a temporary file in the destination directory with Zstandard
compression, close it successfully, and then use `os.replace` for atomic publication. Reads
validate the complete canonical schema and schema version before using bounded Arrow batches to
reconstruct `Bar` objects.

Any material deviation from:

* UTC timestamp storage;
* atomic writes;
* canonical schema;
* one-pass bounded writing;
* explicit overwrite policy

must be documented before SPEC-005 is marked complete.

---

## 36. Completion Summary

Status: Completed

Files created:

* `src/quantforge/data/parquet.py`
* `tests/test_parquet_market_data_store.py`

Files modified:

* `pyproject.toml`
* `docs/specs/SPEC-005-parquet-storage-layer.md`
* `docs/specs/INDEX.md`
* `ARCHITECTURE.md`
* `docs/ENGINEERING_LOG.md`

Runtime dependencies:

* `pyarrow==25.0.1` for direct Arrow schema construction and Parquet persistence.

Public API:

* `quantforge.data.parquet.ParquetMarketDataStore(path: str | Path)`
* `write_bars(bars: Iterable[Bar], *, overwrite: bool = False) -> int`
* `iter_bars() -> Iterator[Bar]`

Tests added:

* 26 deterministic tests covering canonical types and metadata, UTC normalization, list, tuple,
  generator and one-pass inputs, bounded batching, empty files, int64 limits, path and overwrite
  behavior, failed-write atomicity, lazy and incremental reads, incompatible and corrupt files,
  domain reconstruction, CSV round trips, and validator integration.

Commands run:

* `.venv/bin/python -m pytest` — 154 passed.
* `.venv/bin/python -m ruff check .` — passed.
* `.venv/bin/python -m ruff format --check .` — passed; 13 files already formatted.
* `.venv/bin/python -m mypy src tests` — passed; no issues in 13 source files.
* `git diff --check` — passed.
* Markdown validation — not run because no Markdown validator is configured.

Known limitations:

* Only one local Parquet file is supported; datasets are not partitioned or cataloged.
* Original timezone names and UTC offsets are normalized to UTC and are not retained.
* Write and read batch sizes and Zstandard compression are internal fixed choices.
* Concurrent writer coordination and filesystem locking are outside SPEC-005.
* Dataset-level validation remains an explicit caller responsibility.

Engineering log entries:

* `DECISION-007 — Use a Versioned PyArrow Schema with UTC Parquet Persistence`

Follow-up specifications:

* None implemented as part of SPEC-005.

Expected next specification:

`SPEC-006 — Dataset Catalog`
