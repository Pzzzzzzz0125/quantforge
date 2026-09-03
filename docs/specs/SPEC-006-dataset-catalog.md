# SPEC-006 — Dataset Catalog

Status: Completed
Owner: Paul
Created: 2026-09-01
Updated: 2026-09-03

## 1. Problem

QuantForge can ingest, validate, and persist canonical market data in versioned Parquet files.

However, persistent files alone do not provide stable dataset identity or provenance.

As the research repository grows, filenames such as:

```text
bars.parquet
bars_v2.parquet
final_bars.parquet
```

are insufficient to answer:

* Which dataset did an experiment use?
* Where did the dataset originate?
* Which symbols does it contain?
* What time period does it cover?
* How many observations does it contain?
* Has the underlying artifact changed since it was registered?
* Which storage schema produced it?

QuantForge needs a local dataset catalog that assigns stable dataset identities and stores reproducibility-oriented metadata about persisted Parquet artifacts.

---

## 2. Goal

Implement a small, versioned local dataset catalog that:

* explicitly registers QuantForge Parquet datasets;
* assigns each registered dataset a stable unique dataset ID;
* records provenance and summary metadata;
* records a SHA-256 fingerprint of the exact Parquet artifact;
* stores paths portably relative to the catalog location;
* supports lookup and deterministic listing;
* can verify whether a registered artifact still matches its recorded fingerprint;
* persists catalog state atomically;
* keeps registered records immutable;
* introduces no new runtime dependency.

The catalog describes datasets.

It does not modify, validate, repair, copy, move, or delete market-data artifacts.

---

## 3. Non-Goals

SPEC-006 does NOT implement:

* DuckDB;
* SQL querying;
* dataset copying;
* dataset deletion;
* dataset mutation;
* record editing;
* aliases or tags;
* dataset version graphs;
* automatic directory scanning;
* automatic discovery;
* feature datasets;
* experiment tracking;
* strategy metadata;
* backtesting;
* remote catalogs;
* cloud storage;
* S3;
* databases;
* concurrent multi-process catalog writers;
* semantic content hashing;
* market-data repair;
* automatic MarketDataValidator execution.

Experiment tracking belongs to a later specification.

---

## 4. Terminology

### Dataset Artifact

The physical Parquet file containing canonical market bars.

### Dataset Record

Immutable metadata describing one registered dataset artifact.

### Dataset ID

Stable QuantForge identifier assigned when an artifact is first registered.

### Fingerprint

SHA-256 digest of the exact Parquet file bytes at registration time.

The fingerprint identifies artifact integrity.

It is not claimed to be a semantic fingerprint of the underlying market observations.

Two Parquet files containing semantically equivalent bars may have different SHA-256 fingerprints.

### Catalog

Versioned JSON metadata containing registered `DatasetRecord` values.

---

## 5. Public API

Preferred conceptual API:

```python
from quantforge.data.catalog import DatasetCatalog

catalog = DatasetCatalog("data/catalog.json")

record = catalog.register_parquet(
    "data/processed/us_equities.parquet",
    source="csv:data/raw/us_equities.csv",
)

record = catalog.get(record.dataset_id)

records = catalog.list_records()

integrity = catalog.verify(record.dataset_id)
```

Supporting immutable public types should include:

```python
DatasetRecord
DatasetIntegrityReport
```

A similarly small API is acceptable if clearly justified.

Do not introduce a generic catalog backend protocol in SPEC-006.

---

## 6. Catalog Storage Format

The catalog is persisted as UTF-8 JSON.

Conceptual representation:

```json
{
  "catalog_version": 1,
  "datasets": [
    {
      "dataset_id": "ds_...",
      "format": "parquet",
      "storage_path": "processed/us_equities.parquet",
      "source": "csv:data/raw/us_equities.csv",
      "file_sha256": "...",
      "byte_size": 123456,
      "row_count": 50000,
      "symbols": ["AAPL", "MSFT"],
      "earliest_timestamp": "2020-01-02T14:30:00+00:00",
      "latest_timestamp": "2026-08-31T20:00:00+00:00",
      "parquet_schema_version": 1,
      "registered_at": "2026-09-01T18:00:00+00:00"
    }
  ]
}
```

The exact serialized formatting is implementation-defined, but:

* catalog version must be explicit;
* encoding must be UTF-8;
* records must deserialize deterministically;
* timestamps must use unambiguous ISO-8601 UTC representations.

---

## 7. Catalog Version

Define centrally:

```text
catalog_version = 1
```

A catalog with a missing or unsupported catalog version must fail clearly.

Do not silently interpret unknown future versions as version 1.

---

## 8. DatasetRecord

`DatasetRecord` should be immutable.

Preferred conceptual fields:

```python
dataset_id: str
format: str
storage_path: str
source: str
file_sha256: str
byte_size: int
row_count: int
symbols: tuple[str, ...]
earliest_timestamp: datetime | None
latest_timestamp: datetime | None
parquet_schema_version: int
registered_at: datetime
```

A convenience property may expose:

```python
unique_symbols
```

as:

```python
len(symbols)
```

Do not store redundant mutable structures.

---

## 9. Dataset ID

Dataset IDs are generated automatically.

Preferred format:

```text
ds_<uuid4 hex>
```

Example:

```text
ds_5e06c5fef7b44cb29d9173cf789c2dbe
```

Requirements:

* IDs must be unique inside a catalog;
* IDs remain stable after registration;
* IDs must not encode mutable path information;
* IDs are not derived from filenames.

The exact artifact fingerprint is stored independently as SHA-256.

---

## 10. Provenance Source

Registration requires:

```python
source: str
```

The value must be a non-empty string after trimming.

Examples:

```text
csv:data/raw/us_equities.csv
manual:research_snapshot
provider:future-provider-name
```

SPEC-006 treats this field as descriptive provenance.

It does not attempt to interpret provider-specific source semantics.

Structured source provenance may be introduced later when external providers exist.

---

## 11. Portable Storage Paths

The catalog must not persist machine-specific absolute paths such as:

```text
/Users/paul/Desktop/QuantForge/data/processed/bars.parquet
```

Instead, store the dataset path relative to the catalog file's parent directory.

Example:

Catalog:

```text
data/catalog.json
```

Artifact:

```text
data/processed/bars.parquet
```

Stored path:

```text
processed/bars.parquet
```

Use a normalized portable textual representation.

POSIX-style path serialization is preferred.

At runtime, the catalog resolves the stored relative path against its own parent directory.

This allows the repository tree to be moved without invalidating every catalog record.

---

## 12. Registration

Preferred API:

```python
register_parquet(
    path: str | Path,
    *,
    source: str,
) -> DatasetRecord
```

Registration must:

1. resolve the artifact location;
2. verify that it is a valid supported QuantForge Parquet market-bar file;
3. inspect the dataset through the existing Parquet storage boundary;
4. compute summary metadata;
5. compute the exact file SHA-256 fingerprint;
6. compute byte size;
7. generate a unique dataset ID;
8. create an immutable `DatasetRecord`;
9. atomically persist the updated catalog;
10. return the record.

The Parquet artifact itself must never be modified during registration.

---

## 13. Registration Summary Metadata

Registration must determine:

```text
row_count
symbols
earliest_timestamp
latest_timestamp
```

The symbol collection must be:

* unique;
* sorted deterministically;
* stored immutably.

For a non-empty dataset:

```text
earliest_timestamp <= latest_timestamp
```

For an empty dataset:

```text
row_count = 0
symbols = ()
earliest_timestamp = None
latest_timestamp = None
```

The catalog must support valid empty Parquet datasets.

---

## 14. Reuse Existing Domain Boundaries

Registration should reuse:

```python
ParquetMarketDataStore
```

or an equivalent existing SPEC-005 boundary to validate and reconstruct canonical bars.

Do not independently reimplement the entire Parquet schema parser inside the catalog.

Catalog registration does not automatically run:

```python
MarketDataValidator
```

A dataset containing duplicate or out-of-order bars may still be cataloged.

The catalog records identity and metadata, not dataset-quality approval.

---

## 15. SHA-256 Fingerprint

The exact artifact must be fingerprinted with SHA-256.

Use streaming file reads.

Do not use:

```python
path.read_bytes()
```

for potentially large market-data artifacts.

Conceptually:

```text
open file
↓
read bounded chunk
↓
update SHA-256
↓
repeat
```

Memory usage for hashing must therefore remain bounded independently of file size.

The complete lowercase hexadecimal digest is stored.

---

## 16. Byte Size

Record the exact file size in bytes at registration time.

The value must be non-negative.

This provides a cheap additional integrity diagnostic but does not replace SHA-256.

---

## 17. Registration Timestamp

`registered_at` means:

> when the artifact was registered with this QuantForge catalog.

It does NOT claim to be:

* market-data creation time;
* exchange timestamp;
* filesystem creation time.

Store `registered_at` as timezone-aware UTC.

---

## 18. Registration Immutability

Existing catalog records must not be silently mutated.

SPEC-006 provides no record-update API.

If the underlying artifact is modified after registration, the existing record remains unchanged and integrity verification detects the mismatch.

---

## 19. Idempotent Same-Artifact Registration

If the same normalized storage path is already registered and the current artifact SHA-256 matches the recorded SHA-256:

```text
register_parquet(...)
```

should return the existing record rather than create a duplicate record.

This makes repeated registration of the same unchanged artifact idempotent.

---

## 20. Changed Artifact at Registered Path

If a path is already registered but its current SHA-256 differs from the registered fingerprint:

registration must fail clearly.

It must not rewrite the old record.

Example:

```text
registered:
processed/bars.parquet
sha256 = AAA

file later changed:
processed/bars.parquet
sha256 = BBB
```

Calling `register_parquet` again must report that the registered artifact has changed.

To register a new dataset version, write the new artifact under a new path and register it separately.

This makes dataset-version changes explicit.

---

## 21. Same Content at Different Paths

SPEC-006 does not need to deduplicate artifacts globally by hash.

Two different storage paths containing identical bytes may receive separate dataset records.

Artifact path and provenance remain meaningful pieces of catalog identity.

---

## 22. Lookup

Preferred API:

```python
catalog.get(dataset_id) -> DatasetRecord
```

An unknown dataset ID must raise `KeyError`.

Do not return `None` silently for an unknown required identifier.

---

## 23. Listing

Preferred API:

```python
catalog.list_records() -> tuple[DatasetRecord, ...]
```

The returned collection must be immutable.

Ordering must be deterministic.

Registration order is acceptable and preferred for version 1.

Repeated loads of an unchanged catalog must produce the same ordering.

---

## 24. Integrity Verification

Preferred API:

```python
catalog.verify(dataset_id) -> DatasetIntegrityReport
```

`DatasetIntegrityReport` should be immutable.

Conceptual fields:

```python
dataset_id: str
path_exists: bool
byte_size_matches: bool
sha256_matches: bool
```

Preferred derived property:

```python
is_intact
```

which is true only when:

```text
path exists
AND
byte size matches
AND
SHA-256 matches
```

An altered or missing artifact should produce an integrity report rather than mutate the dataset record.

An unknown dataset ID still raises `KeyError`.

---

## 25. Verification Hashing

Integrity verification must also hash large files incrementally.

Do not load the entire artifact into memory.

If the file no longer exists:

```text
path_exists = False
byte_size_matches = False
sha256_matches = False
is_intact = False
```

Verification of a missing registered artifact should return a report rather than convert the missing file into an unknown dataset ID error.

---

## 26. Catalog Construction

Preferred:

```python
DatasetCatalog(path: str | Path)
```

Construction must not immediately access the filesystem.

The catalog file is read when an operation requires its contents.

This keeps construction lazy and testable.

---

## 27. Missing Catalog

A nonexistent catalog file represents an empty catalog.

Therefore:

```python
DatasetCatalog(...).list_records()
```

returns:

```python
()
```

before anything has been registered.

The first successful registration creates the catalog file.

The catalog parent directory must already exist.

SPEC-006 does not silently create arbitrary directory trees.

---

## 28. Invalid Catalog

A catalog file that exists but contains:

* invalid JSON;
* missing required top-level structure;
* unsupported catalog version;
* malformed record fields;
* duplicate dataset IDs;

must fail clearly.

Do not silently reset a damaged catalog to empty state.

That could destroy provenance.

---

## 29. Atomic Catalog Persistence

Catalog updates must use atomic replacement.

Preferred sequence:

```text
read existing catalog
↓
create updated in-memory catalog state
↓
serialize to temporary file in same directory
↓
flush/close successfully
↓
os.replace(temp, catalog)
```

If persistence fails:

* the previous catalog must remain unchanged;
* temporary files should be cleaned where practical;
* a partially written catalog must never become authoritative.

No database transaction framework is required.

---

## 30. Registration Failure Atomicity

If registration fails because of:

* invalid Parquet;
* unsupported Parquet schema;
* hashing failure;
* invalid source;
* catalog serialization failure;
* catalog publication failure;

the existing catalog must remain unchanged.

The dataset artifact must also remain untouched.

---

## 31. Catalog Serialization

Serialized JSON should be deterministic enough for review and Git diffs.

Preferred:

```text
UTF-8
indentation
stable field layout
final newline
```

Byte-for-byte deterministic timestamps are not required across separate registrations because `registered_at` intentionally differs.

Existing unchanged records should not be rewritten with semantically different values.

---

## 32. Error Handling

### Invalid Source

Blank or non-string source values must fail clearly.

### Missing Dataset Artifact

Registration of a missing Parquet artifact should preserve a meaningful filesystem error such as `FileNotFoundError`.

### Invalid Parquet

Existing SPEC-005 schema/version failures should remain understandable.

### Unknown Dataset ID

`get` and `verify` raise `KeyError`.

### Corrupt Catalog

Raise a clear catalog parsing/validation error.

Preserve the underlying JSON exception as the cause where useful.

### Broad Exception Handling

Do not catch unrelated programming exceptions and convert all failures into generic `ValueError`.

---

## 33. Complexity

For registering a dataset containing `n` bars and a file of `b` bytes:

```text
metadata scan: O(n)
file fingerprint: O(b)
```

Memory should be approximately:

```text
O(k)
```

for `k` unique symbols plus bounded read/hash buffers.

Do not retain all `Bar` objects.

Catalog loading itself may be:

```text
O(r)
```

for `r` catalog records.

This is acceptable for a local version-1 metadata catalog.

---

## 34. DatasetRecord Invariants

A valid record must satisfy:

```text
dataset_id is non-empty
format == "parquet"
storage_path is relative
source is non-empty
file_sha256 is exactly 64 lowercase hexadecimal characters
byte_size >= 0
row_count >= 0
symbols are sorted and unique
parquet_schema_version is supported
registered_at is timezone-aware
```

For empty datasets:

```text
row_count == 0
symbols == ()
earliest_timestamp is None
latest_timestamp is None
```

For non-empty datasets:

```text
earliest_timestamp is not None
latest_timestamp is not None
earliest_timestamp <= latest_timestamp
```

---

## 35. No Quality Approval Semantics

A dataset appearing in the catalog does NOT mean:

```text
validated for trading
clean
duplicate-free
ordered
research-approved
```

Catalog registration means only:

> QuantForge successfully identified and recorded this supported dataset artifact.

Quality validation remains explicitly separate.

---

## 36. Tests

Tests must be deterministic and use temporary local files.

At minimum cover:

* lazy catalog construction;
* missing catalog behaves as empty;
* first registration creates catalog;
* immutable dataset record;
* generated dataset ID;
* non-empty source validation;
* relative path persistence;
* no absolute machine path in JSON;
* SHA-256 correctness;
* streaming hash behavior;
* byte size;
* row count;
* sorted unique symbols;
* earliest timestamp;
* latest timestamp;
* empty Parquet dataset;
* UTC registration timestamp;
* lookup;
* unknown lookup;
* deterministic listing;
* immutable list return type;
* idempotent same-path/same-hash registration;
* same path with changed artifact rejected;
* same bytes at different paths allowed;
* verify intact artifact;
* verify modified artifact;
* verify missing artifact;
* unsupported catalog version;
* malformed JSON;
* malformed record;
* duplicate dataset IDs;
* invalid Parquet registration;
* duplicate/out-of-order market data may still be registered;
* catalog unchanged after failed registration;
* atomic catalog replacement;
* temporary-file cleanup;
* no new runtime dependency.

---

## 37. Integration Tests

### Parquet Integration

Create a dataset with:

```python
ParquetMarketDataStore
```

then register it and verify all summary metadata.

### CSV → Parquet → Catalog

Stream:

```text
CSVMarketDataProvider
→ ParquetMarketDataStore
→ DatasetCatalog
```

and confirm the resulting record describes the persisted artifact correctly.

### Validator Separation

Create a valid Parquet artifact containing dataset-level duplicate or ordering defects.

Register it successfully.

Then independently run:

```python
MarketDataValidator
```

to confirm cataloging and quality validation remain separate responsibilities.

---

## 38. Acceptance Criteria

* [x] Versioned JSON catalog exists.
* [x] No new runtime dependency is introduced.
* [x] `DatasetCatalog` exists.
* [x] `DatasetRecord` is immutable.
* [x] `DatasetIntegrityReport` is immutable.
* [x] Catalog construction is filesystem-lazy.
* [x] Missing catalog behaves as empty.
* [x] First successful registration creates the catalog.
* [x] Parent directories are not silently created.
* [x] Registration accepts supported QuantForge Parquet artifacts.
* [x] Registration requires non-empty provenance source.
* [x] Dataset IDs are generated uniquely.
* [x] IDs remain stable after registration.
* [x] Artifact paths are stored relative to the catalog.
* [x] Absolute machine-specific paths are not persisted.
* [x] SHA-256 fingerprint is stored.
* [x] SHA-256 is calculated incrementally.
* [x] Byte size is recorded.
* [x] Row count is recorded.
* [x] Symbols are stored sorted and unique.
* [x] Earliest timestamp is recorded.
* [x] Latest timestamp is recorded.
* [x] Empty datasets are supported.
* [x] Parquet schema version is recorded.
* [x] Registration timestamp is UTC-aware.
* [x] Same-path unchanged registration is idempotent.
* [x] Same registered path with changed bytes is rejected.
* [x] Existing records are not mutated.
* [x] Same content at another path may be separately registered.
* [x] Lookup by dataset ID works.
* [x] Unknown dataset ID raises `KeyError`.
* [x] Listing is immutable and deterministic.
* [x] Integrity verification detects unchanged artifact.
* [x] Integrity verification detects modified artifact.
* [x] Integrity verification detects missing artifact.
* [x] Corrupt catalog does not silently reset to empty.
* [x] Unsupported catalog version fails clearly.
* [x] Malformed records fail clearly.
* [x] Duplicate dataset IDs fail clearly.
* [x] Invalid Parquet registration leaves catalog unchanged.
* [x] Dataset-level defects are not automatically repaired or rejected.
* [x] Catalog writes are atomic.
* [x] Failed catalog publication preserves existing catalog.
* [x] Temporary catalog files are cleaned where practical.
* [x] Dataset artifacts are never modified by catalog operations.
* [x] CSV → Parquet → Catalog integration is tested.
* [x] Parquet → Catalog → Validator separation is tested.
* [x] pytest passes.
* [x] Ruff lint passes.
* [x] Ruff formatting passes.
* [x] strict mypy passes.
* [x] `git diff --check` passes.
* [x] specification index is updated.
* [x] architecture documentation reflects only implemented behavior.
* [x] meaningful design decisions and bugs are recorded.

---

## 39. Known Version-1 Tradeoffs

SPEC-006 intentionally accepts:

```text
full metadata scan during registration
full artifact hashing during registration
single JSON catalog file
no writer locking across processes
no catalog query engine
no automatic dataset discovery
```

These are acceptable for the current local research workflow.

Optimization should follow measured need.

---

## 40. Engineering Decision Expected

Record the next appropriate engineering decision explaining why QuantForge uses:

```text
immutable catalog records
+ relative paths
+ SHA-256 artifact fingerprints
+ atomic versioned JSON persistence
```

for the initial dataset catalog.

---

## 41. Dependencies

Depends on:

* SPEC-002 — Canonical Market Bar Model
* SPEC-003 — CSV Market Data Provider
* SPEC-004 — Market Data Validation
* SPEC-005 — Parquet Storage Layer

New runtime dependencies:

```text
none
```

---

## 42. Completion Summary

Status: Completed

Files created:

* `src/quantforge/data/catalog.py`
* `tests/test_dataset_catalog.py`

Files modified:

* `docs/specs/SPEC-006-dataset-catalog.md`
* `docs/specs/INDEX.md`
* `ARCHITECTURE.md`
* `docs/ENGINEERING_LOG.md`

Public API:

* `DatasetCatalog(path: str | Path)`
* `register_parquet(path: str | Path, *, source: str) -> DatasetRecord`
* `get(dataset_id: str) -> DatasetRecord`
* `list_records() -> tuple[DatasetRecord, ...]`
* `verify(dataset_id: str) -> DatasetIntegrityReport`
* Immutable `DatasetRecord` and `DatasetIntegrityReport` values.

Catalog format:

* UTF-8, indented JSON with a final newline and `catalog_version = 1`.
* A registration-order `datasets` array containing immutable identity, relative location,
  provenance, exact fingerprint and byte size, summary metadata, Parquet schema version, and UTC
  registration time.

Tests added:

* 30 deterministic tests covering lazy construction, registration and summaries, immutable
  models, provenance validation, portable paths, empty datasets, idempotency, changed artifacts,
  UUID collision handling, bounded SHA-256 hashing, intact/modified/missing integrity states,
  corrupt catalog validation, invalid Parquet atomicity, failed JSON serialization/publication,
  temporary cleanup, dataset-quality separation, and CSV → Parquet → Catalog integration.

Commands run:

* `.venv/bin/python -m pytest` — 184 passed.
* `.venv/bin/python -m ruff check .` — passed.
* `.venv/bin/python -m ruff format --check .` — passed; 15 files already formatted.
* `.venv/bin/python -m mypy src tests` — passed; no issues in 15 source files.
* `git diff --check` — passed.
* Markdown validation — not run because no Markdown validator is configured.

Known limitations:

* Registration performs one complete Parquet metadata scan and one complete artifact hash pass.
* The whole JSON catalog is loaded and rewritten for each new registration.
* Multi-process writer locking, automatic discovery, record mutation/deletion, semantic hashing,
  remote catalogs, and query APIs are intentionally unsupported.

Engineering log entries:

* `DECISION-008 — Use Immutable Records and Exact Artifact Fingerprints`

Follow-up specifications:

* None implemented as part of SPEC-006.

Expected next specification:

`SPEC-007 — Feature Interface`
