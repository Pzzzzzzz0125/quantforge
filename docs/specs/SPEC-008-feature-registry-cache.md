# SPEC-008 — Feature Registry & Cache

Status: Completed
Owner: Paul
Created: 2026-09-09
Updated: 2026-09-09

## 1. Problem

SPEC-007 established immutable causal feature-domain contracts:

* `FeatureSpec`
* `FeatureWindow`
* `FeatureValue`
* `Feature`

QuantForge still lacks infrastructure for:

* registering feature implementations under stable identities;
* retrieving features by logical name;
* preventing silent feature-name collisions;
* reusing already-computed feature results;
* distinguishing a cache miss from a cached unavailable (`None`) feature result;
* ensuring cached results are tied to the exact feature input that produced them.

Without this layer, future feature engines and strategies could independently manage feature implementations and caching, increasing duplication and correctness risk.

---

## 2. Goal

Implement two small in-memory components:

* `FeatureRegistry`
* `FeatureCache`

The registry manages feature implementations by stable feature name.

The cache stores results for exact combinations of:

```text
FeatureSpec + FeatureWindow
```

The cache must preserve the distinction between:

```text
cache miss
```

and:

```text
cached None
```

The implementation prioritizes cache correctness and deterministic behavior over premature optimization.

---

## 3. Non-Goals

SPEC-008 does NOT implement:

* feature computation orchestration;
* feature engine;
* batch feature computation;
* concrete financial indicators;
* returns;
* momentum;
* volatility;
* moving averages;
* cross-sectional features;
* persistence;
* disk cache;
* Redis;
* database cache;
* Parquet feature storage;
* dependency graphs;
* parallel feature computation;
* feature invalidation across processes;
* TTL behavior;
* LRU eviction;
* cache-size limits;
* distributed caching;
* strategy interfaces;
* machine learning;
* experiment tracking.

This specification introduces registration and memoization primitives only.

---

## 4. Terminology

### Registry

A deterministic mapping from a stable feature name to one feature implementation.

### Cache

An in-memory mapping from exact feature computation inputs to the already-computed result.

### Cache Hit

The exact feature specification and exact causal feature window were previously stored.

### Cache Miss

No result exists for that exact key.

### Cached Unavailable Result

A feature was evaluated but returned:

```python
None
```

for example during warm-up.

This is different from a cache miss.

---

## 5. Feature Identity

SPEC-007 defines:

```python
FeatureSpec(
    name=...,
    lookback_bars=...,
)
```

For SPEC-008, the immutable `FeatureSpec` is part of cache identity.

The feature name remains the registry identity.

Within one registry:

> One feature name must correspond to exactly one registered feature implementation.

The registry must never silently overwrite an existing feature.

Feature authors are responsible for assigning distinct stable names to semantically distinct configured features.

For example:

```text
momentum_20
momentum_60
```

should be distinct names.

A feature implementation that changes semantics while retaining the same `FeatureSpec` violates the feature contract.

---

## 6. FeatureRegistry

Preferred public API:

```python
from quantforge.features import FeatureRegistry

registry = FeatureRegistry()

registry.register(feature)

feature = registry.get("current_close")

specs = registry.list_specs()
```

The registry is in-memory only.

Construction requires no filesystem or network access.

---

## 7. Registry Registration

Preferred method:

```python
register(feature: Feature) -> None
```

Registration must:

1. obtain the feature's `FeatureSpec`;
2. verify that the exposed spec is actually a `FeatureSpec`;
3. use `spec.name` as the registry key;
4. reject duplicate names;
5. retain deterministic registration order.

The registry must not compute the feature during registration.

---

## 8. Duplicate Feature Names

If a feature name is already registered:

```python
registry.register(second_feature)
```

must fail clearly.

Preferred exception:

```python
ValueError
```

This applies even if the exact same object is registered twice.

Silent replacement is prohibited.

Example:

```text
registered: momentum_20
attempted:  momentum_20
→ error
```

This protects stable feature identity.

---

## 9. Registry Lookup

Preferred:

```python
registry.get(name: str) -> Feature
```

Unknown names must raise:

```python
KeyError
```

Do not return `None` for an unknown required feature.

Feature names supplied to lookup should follow the canonical feature-name rules from SPEC-007.

Do not silently trim or lowercase lookup names.

---

## 10. Registry Listing

Preferred:

```python
registry.list_specs() -> tuple[FeatureSpec, ...]
```

Requirements:

* immutable result;
* registration order preserved;
* no implementation-specific mutable dictionary view exposed.

An empty registry returns:

```python
()
```

---

## 11. Registry Size

A minimal convenience API such as:

```python
len(registry)
```

is desirable.

No additional query language is required.

---

## 12. FeatureCache

Preferred public API:

```python
from quantforge.features import FeatureCache

cache = FeatureCache()

cache.put(feature.spec, window, result)

result = cache.get(feature.spec, window)
```

where:

```python
result: float | None
```

The cache is process-local and in-memory.

---

## 13. Exact Cache Key

The cache key must contain:

```text
FeatureSpec
+
FeatureWindow
```

Conceptually:

```python
(feature_spec, feature_window)
```

This intentionally includes the complete immutable window rather than only:

```text
feature name + symbol + as_of
```

because two datasets may contain different historical observations for the same symbol and timestamp.

Example:

```text
Feature:
momentum_20

Symbol:
AAPL

As-of:
2026-09-09

Dataset A:
Sep 8 close = 100

Dataset B:
Sep 8 close = 105
```

These must not share a cached result merely because feature name, symbol, and as-of timestamp match.

Exact `FeatureWindow` identity/equality prevents that unsafe reuse.

---

## 14. Cache Correctness Over Optimization

Using the complete immutable `FeatureWindow` in the key may require hashing the contained bars.

This cost is acceptable for SPEC-008.

Do not replace exact input identity with a weaker key merely to improve hypothetical performance.

Future profiling may justify:

* precomputed window fingerprints;
* dataset-aware keys;
* engine-scoped caches;
* rolling-state features;

but those optimizations must preserve equivalent correctness guarantees.

---

## 15. Cache Put

Preferred:

```python
put(
    spec: FeatureSpec,
    window: FeatureWindow,
    value: float | None,
) -> None
```

Requirements:

* `spec` must be `FeatureSpec`;
* `window` must be `FeatureWindow`;
* `value` must be a finite Python `float` or `None`;
* integers must not be silently accepted as floats;
* NaN and infinity must be rejected.

This mirrors the numeric semantics of `FeatureValue`.

---

## 16. Cached None

The cache must support:

```python
cache.put(spec, window, None)
```

This represents:

> The feature was computed for this exact window and produced no available value.

This commonly occurs during warm-up.

Retrieving that key must return:

```python
None
```

without treating it as a miss.

---

## 17. Cache Miss

Preferred:

```python
cache.get(spec, window)
```

raises:

```python
KeyError
```

when the exact key does not exist.

This deliberately distinguishes:

```text
KeyError → not cached
None     → cached unavailable result
float    → cached available result
```

Do not use `dict.get()` semantics in the public interface if it makes miss and cached `None` ambiguous.

---

## 18. Cache Replacement

Calling:

```python
cache.put(spec, window, value)
```

for an already-existing exact key must not silently replace a different result.

Preferred behavior:

* if the same key is already cached with an equal value, the operation is idempotent;
* if the same key is already cached with a different value, raise `ValueError`.

Examples:

```text
cached 1.25
put 1.25
→ allowed / no change
```

```text
cached None
put None
→ allowed / no change
```

```text
cached 1.25
put 1.30
→ error
```

```text
cached None
put 1.25
→ error
```

This helps detect violations of feature determinism.

---

## 19. Cache Lookup Must Be Exact

Any difference in the `FeatureSpec` or `FeatureWindow` must result in a distinct key.

Examples that must not collide:

* different feature name;
* different lookback;
* different symbol;
* different as-of timestamp;
* different bar count;
* different historical timestamp;
* different OHLC value;
* different volume.

Equivalent immutable specs and equivalent windows may share the same cached result.

---

## 20. Cache Size

Support:

```python
len(cache)
```

where the result is the number of exact cached computation keys.

A cached `None` counts as one entry.

---

## 21. Cache Clear

Preferred:

```python
cache.clear() -> None
```

After clearing:

```python
len(cache) == 0
```

and all previous lookups miss.

No selective invalidation API is required in SPEC-008.

---

## 22. No Computation Inside Cache

`FeatureCache` must not call:

```python
feature.compute(...)
```

It stores and retrieves results only.

SPEC-008 intentionally does not introduce:

```text
FeatureEvaluator
FeatureEngine
compute_or_cache
```

Those orchestration responsibilities belong to a future specification.

---

## 23. No Registry/Cache Coupling

`FeatureRegistry` and `FeatureCache` should remain separate components.

The cache should not require a registry reference.

The registry should not own a cache.

A future feature engine may compose:

```text
Registry
+
Cache
+
FeatureWindow construction
+
Feature computation
```

This specification does not introduce that orchestrator yet.

---

## 24. Immutability of Inputs

Neither component may mutate:

* `FeatureSpec`;
* `FeatureWindow`;
* `Bar`;
* feature implementation state.

The registry stores references to feature implementations but must not modify them.

The cache stores immutable key objects and scalar/None results.

---

## 25. Determinism

Given an unchanged registry:

```text
same feature name
→ same registered object
```

Given an unchanged cache:

```text
same FeatureSpec
+
same FeatureWindow
→ same cached result
```

Registry listing must remain deterministic.

---

## 26. Error Handling

### Invalid Registry Feature

If the registered object's exposed `spec` is not a `FeatureSpec`, fail clearly with `TypeError`.

Do not silently construct or normalize a spec.

### Duplicate Registry Name

Raise `ValueError`.

### Unknown Feature

Raise `KeyError`.

### Invalid Cache Spec

Raise `TypeError`.

### Invalid Cache Window

Raise `TypeError`.

### Invalid Cached Value Type

Raise `TypeError`.

### Non-Finite Cached Value

Raise `ValueError`.

### Conflicting Existing Cache Value

Raise `ValueError`.

Do not catch unrelated programming exceptions broadly.

---

## 27. Runtime Protocol Scope

SPEC-008 does not require expensive runtime structural inspection of every possible feature implementation.

Static compatibility remains primarily enforced through the `Feature` protocol and strict mypy.

The registry should minimally validate the stable runtime metadata it relies upon:

```python
feature.spec
```

must be a valid `FeatureSpec`.

Do not introduce reflection-heavy runtime validation.

---

## 28. Module Structure

Preferred:

```text
src/quantforge/features/
    __init__.py
    base.py
    registry.py
    cache.py
```

Public imports may be re-exported from:

```python
quantforge.features
```

Preferred:

```python
from quantforge.features import (
    Feature,
    FeatureCache,
    FeatureRegistry,
    FeatureSpec,
    FeatureValue,
    FeatureWindow,
)
```

Avoid circular dependencies.

---

## 29. Dependency Policy

SPEC-008 introduces no runtime dependencies.

Use:

* standard library;
* existing QuantForge feature-domain types.

Do not add:

* NumPy;
* Pandas;
* Polars;
* Redis clients;
* caching libraries.

---

## 30. Registry Tests

Tests must cover at least:

* empty registry;
* successful registration;
* lookup returns registered feature;
* multiple feature registrations;
* deterministic registration order;
* immutable tuple listing;
* duplicate name rejected;
* same object registered twice rejected;
* unknown name raises `KeyError`;
* invalid lookup name not silently normalized;
* invalid exposed spec rejected;
* registry length;
* feature is not computed during registration.

---

## 31. Cache Tests

Tests must cover at least:

* empty cache;
* cache miss raises `KeyError`;
* float value round trip;
* cached `None` round trip;
* miss distinguishable from cached `None`;
* integer value rejected;
* NaN rejected;
* positive infinity rejected;
* negative infinity rejected;
* invalid spec type rejected;
* invalid window type rejected;
* cache length;
* cached `None` counts toward length;
* clear;
* same exact key + same value is idempotent;
* same exact key + conflicting float rejected;
* cached None replaced by float rejected;
* cached float replaced by None rejected.

---

## 32. Exact-Key Regression Tests

Explicitly verify that all of the following produce different cache keys.

### Different Feature Name

```text
return_1
vs
momentum_20
```

### Different Lookback

Equivalent name is normally not expected in production, but structurally different `FeatureSpec` values must remain distinct cache keys.

### Different Symbol

```text
AAPL
vs
MSFT
```

### Different As-Of Timestamp

```text
09:30
vs
09:31
```

### Different Historical Price

Two windows with the same:

```text
feature name
symbol
as_of
```

but a different earlier close must not collide.

### Different Historical Volume

Likewise, different volume must not collide.

### Equivalent Window

Separately constructed but value-equal immutable windows should resolve to the same cache entry.

---

## 33. Causal Safety

SPEC-008 does not construct feature windows.

Therefore it does not independently guarantee that a caller chose the correct as-of window.

It preserves the causal semantics of whatever valid `FeatureWindow` it receives.

Importantly, it must never weaken input identity by caching solely on:

```text
feature + symbol + as_of
```

because doing so could reuse a result computed from different historical information.

The future feature engine remains responsible for causal window construction.

---

## 34. Complexity

Registry:

```text
register: average O(1)
get:      average O(1)
```

Cache dictionary lookup is average constant-time after key hashing.

However, hashing a `FeatureWindow` may require work proportional to the number of contained bars:

```text
window hash: O(w)
```

for window length `w`.

This is an accepted correctness-first tradeoff in SPEC-008.

Memory usage grows with registered features and cached entries.

No eviction policy is introduced yet.

---

## 35. Security / Secrets

No credentials, filesystem access, external services, or network access are required.

---

## 36. Alternatives Considered

### Cache by Feature Name + Symbol + As-Of

Rejected.

This can produce false cache hits when the underlying historical window differs.

### Cache by Dataset ID

Potentially useful later, but SPEC-007 windows are not currently tied to a dataset catalog record.

Introducing dataset identity into feature computation now would unnecessarily couple the feature layer to persistence infrastructure.

Deferred.

### Hash a Serialized Window with SHA-256

Provides stable fingerprints but adds unnecessary serialization and hashing overhead for a process-local cache.

Deferred unless future persistent caching requires it.

### Use FeatureSpec + Exact Immutable FeatureWindow

Selected.

It provides the strongest simple correctness semantics using existing immutable domain objects.

### Use `None` for Both Miss and Warm-Up

Rejected because the two states are semantically different.

### Overwrite Existing Cached Values

Rejected because conflicting outputs for identical immutable inputs may indicate non-deterministic or defective feature behavior.

---

## 37. Invariants

Registry invariants:

* every registered key equals its feature's registered `FeatureSpec.name`;
* no duplicate feature names;
* registration order deterministic;
* lookup never silently substitutes another feature.

Cache invariants:

* every key is an exact `(FeatureSpec, FeatureWindow)` pair;
* every stored value is finite `float` or `None`;
* cached `None` is a real entry;
* absent entries raise `KeyError`;
* an existing exact key cannot silently change value.

---

## 38. Acceptance Criteria

* [x] `FeatureRegistry` exists.
* [x] `FeatureCache` exists.
* [x] both are in-memory only.
* [x] no runtime dependency is introduced.
* [x] registry accepts `Feature` implementations.
* [x] registry validates exposed `FeatureSpec`.
* [x] registry uses feature name as stable lookup identity.
* [x] registry does not compute features during registration.
* [x] duplicate names are rejected.
* [x] repeated registration of the same object is rejected.
* [x] unknown registry names raise `KeyError`.
* [x] registry does not silently normalize lookup names.
* [x] registry listing is immutable.
* [x] registry listing preserves registration order.
* [x] registry length is available.
* [x] cache keys include complete `FeatureSpec`.
* [x] cache keys include complete `FeatureWindow`.
* [x] cache does not key only by symbol/as-of.
* [x] exact historical input differences cause cache misses.
* [x] equal independently constructed windows can produce cache hits.
* [x] cached available values are Python floats.
* [x] cached values must be finite.
* [x] integer cached values are rejected.
* [x] cached `None` is supported.
* [x] cached `None` is distinguishable from a miss.
* [x] cache misses raise `KeyError`.
* [x] same key/same result insertion is idempotent.
* [x] same key/different result insertion is rejected.
* [x] cached `None` cannot silently become a float.
* [x] cached float cannot silently become `None`.
* [x] cache length counts exact stored keys.
* [x] cached `None` counts as an entry.
* [x] cache clear works.
* [x] cache does not compute features.
* [x] registry does not own cache.
* [x] cache does not require registry.
* [x] FeatureSpec inputs are never mutated.
* [x] FeatureWindow inputs are never mutated.
* [x] feature objects are not mutated by registry.
* [x] deterministic registry behavior is tested.
* [x] different feature names do not collide.
* [x] different lookbacks do not collide.
* [x] different symbols do not collide.
* [x] different as-of timestamps do not collide.
* [x] different historical prices do not collide.
* [x] different historical volume does not collide.
* [x] equivalent specs/windows reuse cached values.
* [x] pytest passes.
* [x] Ruff lint passes.
* [x] Ruff formatting passes.
* [x] strict mypy passes.
* [x] `git diff --check` passes.
* [x] specification index is updated.
* [x] architecture documentation reflects only implemented architecture.
* [x] meaningful decisions or bugs are recorded.

---

## 39. Engineering Decision Expected

Record the next appropriate engineering decision explaining why QuantForge initially uses:

```text
exact immutable FeatureSpec + FeatureWindow cache keys
+
explicit KeyError for misses
+
cached None support
+
conflicting-result rejection
```

instead of a weaker feature/symbol/timestamp cache identity.

---

## 40. Dependencies

Depends on:

* SPEC-007 — Feature Interface
* SPEC-002 — Canonical Market Bar Model indirectly through FeatureWindow

New runtime dependencies:

```text
none
```

Expected next specification:

```text
SPEC-009 — Strategy Interface
```

Do not begin SPEC-009 during this implementation.

---

## 41. Completion Summary

Status: Completed

Files created:

* `src/quantforge/features/registry.py`
* `src/quantforge/features/cache.py`
* `tests/test_feature_registry_cache.py`
* `docs/specs/SPEC-008-feature-registry-cache.md`

Files modified:

* `src/quantforge/features/__init__.py`
* `ARCHITECTURE.md`
* `docs/ENGINEERING_LOG.md`
* `docs/specs/INDEX.md`

Public API:

* `quantforge.features.FeatureRegistry`
* `quantforge.features.FeatureCache`

Registry behavior:

* Registration captures a valid immutable `FeatureSpec`, keys by its canonical name, preserves
  registration order, and never calls `compute`.
* Duplicate names and repeated registration of the same object raise `ValueError`.
* Exact-name lookup returns the registered object; missing or noncanonical lookup strings raise
  `KeyError`.
* `list_specs()` returns an immutable tuple and `len(registry)` reports registered implementations.

Cache-key design:

* Each key is the exact tuple `(FeatureSpec, FeatureWindow)`, so every immutable spec field and every
  field of every historical `Bar` participates in equality and hashing.
* Cached values are finite Python `float` values or `None`; a miss raises `KeyError`.
* Repeating the same key/result is idempotent, while a conflicting result raises `ValueError`.

Tests added:

* 38 deterministic cases cover registry ordering and collisions, exact cache identity, cached
  `None`, value validation, result conflicts, clearing, input immutability, and no computation.
* Explicit regressions prove that otherwise-identical symbol/as-of windows with a different
  historical price or volume miss independently.

Commands run:

* `.venv/bin/python -m pytest` — 272 passed.
* `.venv/bin/python -m ruff check .` — passed.
* `.venv/bin/python -m ruff format --check .` — passed.
* `.venv/bin/python -m mypy src tests` — passed in strict mode.
* `git diff --check` — passed.

Known limitations:

* Cache memory grows without eviction and is process-local only.
* Hashing a window is `O(w)` in its number of bars; this correctness-first implementation does not
  precompute fingerprints.
* Registry and cache do not orchestrate feature computation or causal-window construction.
* Concurrent access guarantees, persistence, invalidation, TTL, LRU, and dependency graphs are not
  provided.

Engineering log entries:

* `DECISION-010 — Cache Exact Immutable Feature Inputs`

Follow-up specifications:

* SPEC-009 may define the strategy interface without adding feature computation orchestration.

Expected next specification:

`SPEC-009 — Strategy Interface`
