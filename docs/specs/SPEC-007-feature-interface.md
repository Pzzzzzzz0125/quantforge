# SPEC-007 — Feature Interface

Status: Completed
Owner: Paul
Created: 2026-09-03
Updated: 2026-09-03

## 1. Problem

QuantForge now has a reliable market-data layer:

```text
CSV ingestion
→ canonical Bar
→ dataset validation
→ Parquet persistence
→ dataset catalog
```

The system does not yet have a standard abstraction for quantitative features.

Without a common feature contract, individual research modules could independently decide:

* what data a feature receives;
* how much historical context is required;
* how unavailable values are represented;
* how feature identity is represented;
* how timestamps are attached to computed values;
* whether future observations can accidentally leak into computation.

That would make feature reuse, caching, testing, and time-safety difficult.

---

## 2. Goal

Introduce the minimal common feature-domain interface required for future quantitative research.

SPEC-007 must define:

* `FeatureSpec`
* `FeatureWindow`
* `FeatureValue`
* `Feature` protocol

The interface must make the feature's evaluation timestamp explicit and provide only a bounded historical window ending at that timestamp.

The design must support future feature registries and caching without implementing them yet.

---

## 3. Non-Goals

SPEC-007 does NOT implement:

* momentum;
* returns;
* moving averages;
* volatility;
* statistical arbitrage;
* technical indicators;
* feature registry;
* feature cache;
* feature persistence;
* batch feature engine;
* Pandas;
* NumPy;
* Polars;
* DuckDB;
* machine learning;
* strategies;
* portfolio construction;
* backtesting;
* cross-sectional ranking;
* feature normalization;
* feature selection.

Concrete financial features belong to later specifications.

SPEC-008 will introduce registry/cache behavior.

---

## 4. Terminology

### Feature

A deterministic quantity computed from market information available at or before a specific evaluation time.

Examples in future specifications may include:

```text
return
momentum
volatility
spread z-score
```

### As-Of Time

The timestamp at which the feature is considered known.

A feature evaluated as of time `t` must not depend on observations after `t`.

### Lookback

Number of canonical bars required for the intended feature calculation.

### Warm-Up

Period during which insufficient historical observations exist to compute a feature.

### Feature Window

An immutable ordered sequence of bars belonging to exactly one symbol, ending at the feature's as-of timestamp.

---

## 5. Time-Safety Principle

Feature computation must be causal.

For an evaluation at timestamp:

```text
t
```

the feature may use:

```text
timestamp <= t
```

but never:

```text
timestamp > t
```

SPEC-007 establishes this boundary structurally through `FeatureWindow`.

The future feature engine is responsible for constructing windows containing only information available as of the evaluation point.

A feature implementation must operate only on the supplied window.

It must not independently reach into a full dataset, provider, catalog, filesystem, network API, or future observations.

---

## 6. FeatureSpec

Introduce an immutable feature specification.

Preferred shape:

```python
@dataclass(frozen=True, slots=True)
class FeatureSpec:
    name: str
    lookback_bars: int
```

### Name

The feature name is its stable logical identity.

Examples:

```text
close_price
return_1
momentum_20
realized_volatility_20
```

Requirements:

* Python `str`;
* non-empty;
* surrounding whitespace rejected rather than silently retained;
* stable and deterministic;
* lowercase snake-case identifiers are preferred.

SPEC-007 should enforce a simple identifier form:

```text
[a-z][a-z0-9_]*
```

Do not introduce arbitrary display names or descriptions yet.

### Lookback

`lookback_bars` must be a Python integer greater than or equal to 1.

Boolean values must be rejected.

Interpretation:

```text
lookback_bars = 1
```

means the feature may be computed from one current bar.

```text
lookback_bars = 20
```

means twenty bars are required for a fully available value.

---

## 7. FeatureWindow

Introduce an immutable window of canonical bars.

Preferred conceptual API:

```python
FeatureWindow(
    bars=(bar1, bar2, ..., current_bar),
)
```

The stored collection must be a tuple.

### Requirements

The window must:

* contain at least one `Bar`;
* contain only canonical `Bar` instances;
* contain exactly one symbol;
* be strictly increasing by timestamp;
* contain no duplicate timestamps;
* remain immutable.

### Derived Properties

Preferred convenience properties:

```python
window.symbol
window.as_of
window.current
window.size
```

where:

```text
symbol  = the common symbol
as_of   = timestamp of the final bar
current = final bar
size    = number of bars
```

### Ordering

For:

```text
09:30
09:31
09:32
```

the window is valid.

For:

```text
09:30
09:32
09:31
```

the window is invalid.

For:

```text
09:30
09:30
```

the window is invalid.

Dataset-level validators remain responsible for diagnosing complete datasets.

`FeatureWindow` validation exists because a feature must never receive an ambiguous time sequence.

---

## 8. Window Construction Responsibility

SPEC-007 does not implement the production feature engine.

Therefore `FeatureWindow` may be constructed directly in tests and research code.

Future feature-engine code will be responsible for selecting the appropriate historical bars.

For a feature evaluated at index `i`, the engine must never include observations after index `i`.

---

## 9. FeatureValue

Introduce an immutable computed feature observation.

Preferred shape:

```python
@dataclass(frozen=True, slots=True)
class FeatureValue:
    feature_name: str
    symbol: str
    timestamp: datetime
    value: float
```

This represents:

> Feature X had numeric value Y for symbol S as of timestamp T.

---

## 10. FeatureValue Validation

### Feature Name

Must satisfy the same logical naming rules as `FeatureSpec.name`.

### Symbol

Must be a normalized non-empty symbol.

The value should already correspond to a canonical `Bar` symbol.

Do not silently normalize inconsistent feature-output metadata.

### Timestamp

Must be timezone-aware using the same awareness rule as `Bar`:

```python
timestamp.tzinfo is not None
and
timestamp.utcoffset() is not None
```

### Numeric Value

`value` must be a Python `float`.

It must be finite.

Reject:

```text
NaN
+Inf
-Inf
```

Do not use NaN as the standard representation for an unavailable feature.

Unavailable features are represented separately as `None`.

---

## 11. Feature Protocol

Preferred conceptual protocol:

```python
class Feature(Protocol):
    @property
    def spec(self) -> FeatureSpec:
        ...

    def compute(self, window: FeatureWindow) -> float | None:
        ...
```

A concrete feature exposes immutable metadata through `spec`.

Its computation receives only a `FeatureWindow`.

---

## 12. Compute Contract

Given:

```python
result = feature.compute(window)
```

the result is either:

```python
float
```

or:

```python
None
```

### Float

A numeric feature is available.

The value must be finite.

### None

The feature is unavailable.

The primary expected reason is insufficient lookback history.

For example:

```text
lookback_bars = 20
window.size = 7
```

may produce:

```python
None
```

Do not substitute:

```text
0
NaN
Inf
```

for an unavailable feature.

---

## 13. Lookback Contract

A conforming feature must not claim a normal available value when the supplied window has fewer bars than:

```python
feature.spec.lookback_bars
```

The normal behavior is:

```python
None
```

when:

```text
window.size < lookback_bars
```

SPEC-007 does not force a base implementation of this check because `Feature` is a protocol.

Concrete feature specifications must test their lookback behavior.

---

## 14. Feature Purity

Feature computation should be deterministic and observationally pure.

Given:

```text
same feature configuration
+
same FeatureWindow
```

the feature should return the same result.

Feature computation must not:

* modify Bars;
* modify the FeatureWindow;
* mutate market-data datasets;
* perform network requests;
* write files;
* read future data;
* depend on wall-clock time;
* depend on hidden global mutable state.

Stateful streaming indicators may be considered later if performance measurements justify them.

SPEC-007 defines the research-facing semantic contract first.

---

## 15. Feature Output Construction

SPEC-007 does not require `Feature.compute()` itself to construct `FeatureValue`.

The future engine may conceptually perform:

```python
raw_value = feature.compute(window)

if raw_value is not None:
    value = FeatureValue(
        feature_name=feature.spec.name,
        symbol=window.symbol,
        timestamp=window.as_of,
        value=raw_value,
    )
```

This keeps authoritative feature metadata tied to the engine's evaluation context.

---

## 16. No Future Access

A feature implementation must not accept:

```text
complete dataset + current index
```

as its public computation contract.

The production feature interface receives only the historical `FeatureWindow`.

This intentionally reduces accidental look-ahead surface area.

SPEC-007 does not claim that Python can technically prevent malicious code from loading external future data.

The contract prevents future observations from being supplied through the normal feature API.

---

## 17. Multiple Symbols

One `FeatureWindow` represents exactly one symbol.

Cross-sectional computations such as:

```text
rank all stocks by momentum at time t
```

are NOT implemented by SPEC-007.

The future architecture may compute per-symbol features first:

```text
AAPL momentum
MSFT momentum
NVDA momentum
```

and then perform cross-sectional operations in a separate layer.

Do not weaken the single-symbol window model prematurely.

---

## 18. Error Handling

Incorrect contract inputs are programming errors and should fail clearly.

Examples:

* invalid `FeatureSpec` name;
* non-positive lookback;
* non-Bar window element;
* mixed symbols;
* duplicate timestamps;
* decreasing timestamps;
* invalid FeatureValue metadata;
* NaN/Inf output values when constructing `FeatureValue`.

Use:

```text
TypeError
```

for fundamentally incorrect Python types.

Use:

```text
ValueError
```

for invalid values of otherwise correct types.

Do not silently repair invalid feature-domain objects.

---

## 19. Immutability

The following must be immutable:

```text
FeatureSpec
FeatureWindow
FeatureValue
```

Preferred implementation:

```python
@dataclass(frozen=True, slots=True)
```

`FeatureWindow.bars` must be a tuple rather than a mutable list.

Hashability is desirable where naturally supported because future registries/caches may use these objects as metadata or keys.

---

## 20. Dependency Policy

SPEC-007 introduces no runtime dependency.

Use:

* standard library;
* existing QuantForge domain types.

Do not add:

* NumPy;
* Pandas;
* SciPy;
* Polars.

Those dependencies should only be introduced when a concrete research requirement justifies them.

---

## 21. Public Module

Preferred location:

```text
src/quantforge/features/base.py
```

with:

```text
src/quantforge/features/__init__.py
```

Preferred imports:

```python
from quantforge.features.base import (
    Feature,
    FeatureSpec,
    FeatureValue,
    FeatureWindow,
)
```

A clean equivalent structure is acceptable.

---

## 22. Example Contract

A test-only feature may look conceptually like:

```python
class CurrentCloseFeature:
    @property
    def spec(self) -> FeatureSpec:
        return FeatureSpec(
            name="current_close",
            lookback_bars=1,
        )

    def compute(self, window: FeatureWindow) -> float | None:
        if window.size < self.spec.lookback_bars:
            return None

        return window.current.close
```

This is an example for testing the interface.

SPEC-007 should not ship concrete quantitative research features solely to demonstrate the API.

---

## 23. Edge Cases

Tests must cover at least:

* valid FeatureSpec;
* invalid empty name;
* whitespace name;
* uppercase/invalid identifier;
* lookback of 1;
* lookback greater than 1;
* zero lookback;
* negative lookback;
* bool lookback;
* valid one-bar window;
* multiple-bar window;
* tuple storage;
* empty window;
* non-Bar window element;
* mixed symbols;
* duplicate timestamp;
* decreasing timestamp;
* timezone-aware as-of value;
* correct current bar;
* correct window size;
* immutable FeatureSpec;
* immutable FeatureWindow;
* immutable FeatureValue;
* valid finite FeatureValue;
* integer FeatureValue rejected;
* NaN rejected;
* positive infinity rejected;
* negative infinity rejected;
* naive FeatureValue timestamp rejected;
* protocol conformance using a test feature;
* insufficient-history feature returns `None`;
* deterministic repeated computation;
* feature cannot mutate supplied window through the public immutable representation.

---

## 24. Testing Strategy

All tests must be deterministic and network-independent.

### Domain Tests

Test validation and immutability of:

```text
FeatureSpec
FeatureWindow
FeatureValue
```

### Protocol Test

Create a small test-only feature conforming to `Feature`.

Verify it can be assigned or passed where the protocol is expected under strict mypy.

### Time-Boundary Test

Construct bars:

```text
09:30
09:31
09:32
```

Construct a window ending at:

```text
09:31
```

Verify the feature receives only:

```text
09:30
09:31
```

and cannot obtain `09:32` through the window.

This test documents the causal usage model.

### Warm-Up Test

Use a test feature with:

```text
lookback_bars = 3
```

Verify:

```text
1 bar → None
2 bars → None
3 bars → numeric value
```

---

## 25. Acceptance Criteria

* [x] Feature package exists.
* [x] `FeatureSpec` exists.
* [x] `FeatureSpec` is immutable.
* [x] feature names are validated.
* [x] `lookback_bars >= 1` is enforced.
* [x] boolean lookback is rejected.
* [x] `FeatureWindow` exists.
* [x] `FeatureWindow` is immutable.
* [x] window bars are stored immutably.
* [x] empty windows are rejected.
* [x] non-Bar elements are rejected.
* [x] mixed-symbol windows are rejected.
* [x] duplicate timestamps are rejected.
* [x] decreasing timestamps are rejected.
* [x] `window.symbol` works.
* [x] `window.as_of` is the final timestamp.
* [x] `window.current` is the final Bar.
* [x] `window.size` is correct.
* [x] `FeatureValue` exists.
* [x] `FeatureValue` is immutable.
* [x] FeatureValue timestamps must be timezone-aware.
* [x] FeatureValue values must be Python floats.
* [x] FeatureValue values must be finite.
* [x] unavailable features use `None` rather than NaN.
* [x] `Feature` protocol exists.
* [x] protocol exposes `spec`.
* [x] protocol exposes `compute(window)`.
* [x] no complete-dataset/current-index API is introduced.
* [x] test-only protocol implementation passes strict mypy.
* [x] warm-up semantics are tested.
* [x] causal-window usage is tested.
* [x] feature computation does not mutate window data.
* [x] no concrete production research indicator is added.
* [x] no feature registry is implemented.
* [x] no cache is implemented.
* [x] no new runtime dependency is introduced.
* [x] pytest passes.
* [x] Ruff lint passes.
* [x] Ruff formatting passes.
* [x] strict mypy passes.
* [x] `git diff --check` passes.
* [x] specification index is updated.
* [x] architecture documentation reflects only implemented architecture.
* [x] meaningful design decisions or bugs are logged.

---

## 26. Performance Considerations

SPEC-007 prioritizes semantic correctness and time safety over premature optimization.

Immutable tuple-based feature windows may require slicing/copying in an initial feature engine.

Do not optimize this interface spec around hypothetical high-frequency performance requirements.

SPEC-008 and later performance work may introduce caching or efficient window construction while preserving the same causal semantics.

Correctness comes first.

---

## 27. Security / Secrets

No credentials, network services, or secrets are involved.

Feature computation must not execute external data as code.

---

## 28. Alternatives Considered

### Give Features the Entire Dataset and Current Index

Example:

```python
compute(dataset, index)
```

Rejected for the primary interface because the feature can accidentally access:

```text
dataset[index + 1]
```

and introduce look-ahead leakage.

### Stateful Feature Objects

Example:

```python
feature.update(bar)
```

This can enforce causal processing and may eventually improve performance.

Deferred because it couples semantic feature definitions to mutable execution state before performance requirements are measured.

### DataFrame-Based Feature API

Rejected for SPEC-007.

It would introduce dependencies and make causal boundaries less explicit.

### Immutable Historical FeatureWindow

Selected.

It makes:

```text
symbol
history
current observation
as-of timestamp
```

explicit while keeping the first research interface small and testable.

---

## 29. Engineering Decision Expected

Record the next appropriate decision describing why QuantForge uses:

```text
immutable single-symbol causal FeatureWindow
+
explicit lookback metadata
+
None for unavailable values
```

instead of exposing a full dataset to feature implementations.

---

## 30. Dependencies

Depends on:

* SPEC-002 — Canonical Market Bar Model

Conceptually integrates later with:

* SPEC-008 — Feature Registry & Cache
* future strategy interfaces
* future experiment tracking

New runtime dependencies:

```text
none
```

---

## 31. Completion Summary

Status: Completed

Files created:

* `src/quantforge/features/__init__.py`
* `src/quantforge/features/base.py`
* `tests/test_feature_interface.py`
* `docs/specs/SPEC-007-feature-interface.md`

Files modified:

* `ARCHITECTURE.md`
* `docs/ENGINEERING_LOG.md`
* `docs/specs/INDEX.md`

Public API:

* `quantforge.features.Feature`
* `quantforge.features.FeatureSpec`
* `quantforge.features.FeatureWindow`
* `quantforge.features.FeatureValue`

Tests added:

* 50 deterministic feature-contract cases covering metadata validation, immutable causal windows,
  feature-value semantics, protocol compatibility, warm-up behavior, and look-ahead boundaries.

Commands run:

* `.venv/bin/python -m pytest` — 234 passed.
* `.venv/bin/python -m ruff check .` — passed.
* `.venv/bin/python -m ruff format --check .` — passed.
* `.venv/bin/python -m mypy src tests` — passed in strict mode.
* `git diff --check` — passed.

Known limitations:

* No production financial feature is implemented.
* Callers construct windows directly until a future engine owns causal window selection.
* The protocol documents finite available outputs, while `FeatureValue` enforces finiteness when an
  output becomes an observation.
* Registry, caching, persistence, cross-sectional computation, and optimized window construction
  remain intentionally unavailable.

Engineering log entries:

* `DECISION-009 — Bound Features to Immutable Causal Windows`

Follow-up specifications:

* SPEC-008 may define feature registry and cache behavior without weakening the causal computation
  contract.

Expected next specification:

`SPEC-008 — Feature Registry & Cache`
