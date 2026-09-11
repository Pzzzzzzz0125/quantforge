# SPEC-009 — Strategy Interface

Status: Completed
Owner: Paul
Created: 2026-09-09
Updated: 2026-09-09

## 1. Problem

QuantForge now has causal feature contracts plus feature registration and caching, but it does not yet have a standard boundary for converting research information into trading opinions.

Without a strategy contract, strategy implementations could independently decide whether to:

* access raw datasets;
* inspect future observations;
* mutate portfolio state;
* create orders directly;
* encode quantities and execution assumptions;
* consume inconsistent feature timestamps;
* return unstructured dictionaries or arbitrary values.

That would couple research logic to portfolio construction and execution.

QuantForge needs a small strategy-domain interface that converts causal feature information into structured signals while remaining completely independent of positions, cash, orders, fills, commissions, and slippage.

---

## 2. Goal

Introduce the minimal strategy-domain contract required for later portfolio construction and event-driven backtesting.

SPEC-009 must define:

* `StrategySpec`
* `StrategyContext`
* `Signal`
* `Strategy` protocol

A strategy receives an immutable causal context containing feature values known as of one explicit timestamp.

A strategy emits immutable alpha signals.

The strategy layer expresses opinions.

It does not express trades.

---

## 3. Core Boundary

The intended architecture is:

```text
Feature computation
      ↓
FeatureValue
      ↓
StrategyContext
      ↓
Strategy
      ↓
Signal
      ↓
future Portfolio Construction
      ↓
future Order
      ↓
future Execution / Fill
```

The strategy layer must not skip downstream boundaries.

---

## 4. Non-Goals

SPEC-009 does NOT implement:

```text
portfolio construction
position sizing
cash management
risk limits
orders
order quantities
market orders
limit orders
fills
execution simulation
commission
slippage
portfolio accounting
event loop
backtesting
concrete momentum strategy
pairs trading
ML models
feature engine
strategy registry
strategy cache
strategy persistence
experiment tracking
```

Those concerns belong to later specifications.

---

## 5. Terminology

### Strategy

A deterministic decision rule that converts causal research information into one or more alpha signals.

### Strategy Context

The information available to a strategy at one explicit evaluation time.

### Signal

A strategy's directional numeric opinion about one symbol at one timestamp.

A signal is not an order.

### Score

A finite dimensionless numeric alpha score.

By convention:

```text
score > 0   bullish
score < 0   bearish
score = 0   neutral
```

The magnitude may represent relative strength according to the concrete strategy's semantics.

SPEC-009 does not impose a universal score range.

---

## 6. StrategySpec

Introduce an immutable specification.

Preferred shape:

```python
@dataclass(frozen=True, slots=True)
class StrategySpec:
    name: str
    required_features: tuple[str, ...]
```

`name` is the stable strategy identity.

Examples:

```text
cross_sectional_momentum
pairs_mean_reversion
ml_stat_arb
```

The strategy name must follow:

```text
[a-z][a-z0-9_]*
```

No silent trimming or lowercasing is permitted.

---

## 7. Required Features

`required_features` describes the logical feature names a strategy expects.

Example:

```python
StrategySpec(
    name="example_strategy",
    required_features=(
        "momentum_20",
        "realized_volatility_20",
    ),
)
```

Requirements:

```text
must be tuple[str, ...]
each name uses canonical feature-name syntax
names must be unique
declared order must be preserved
```

An empty tuple is valid.

SPEC-009 does not resolve these names through `FeatureRegistry`.

A future orchestrator will perform that integration.

---

## 8. StrategyContext

Introduce an immutable context representing feature information available at exactly one strategy evaluation time.

Preferred conceptual shape:

```python
@dataclass(frozen=True, slots=True)
class StrategyContext:
    as_of: datetime
    features: tuple[FeatureValue, ...]
```

The context may contain feature values for multiple symbols.

This intentionally supports future:

```text
cross-sectional strategies
relative-value strategies
pairs strategies
multi-asset strategies
```

without exposing complete historical datasets.

---

## 9. Context As-Of Time

`as_of` must:

```text
be a datetime
be timezone-aware
have utcoffset() != None
```

Every included `FeatureValue.timestamp` must represent the same instant as:

```text
context.as_of
```

Example:

```text
context.as_of = 2026-09-09 20:00 UTC

AAPL momentum timestamp = same instant
MSFT momentum timestamp = same instant
```

A feature from an earlier or later timestamp cannot be mixed into that context.

---

## 10. Context Feature Collection

`features` must:

```text
be a tuple
contain only FeatureValue
remain immutable
```

An empty feature tuple is valid.

A context must not contain duplicate logical observations for:

```text
(feature_name, symbol)
```

because the strategy would otherwise have ambiguous input.

Example invalid context:

```text
momentum_20 / AAPL / 1.2
momentum_20 / AAPL / 1.3
```

even if both share the same timestamp.

---

## 11. Feature Absence

SPEC-007 represents unavailable feature computation using:

```python
None
```

and therefore no `FeatureValue` exists for that unavailable result.

StrategyContext contains only available `FeatureValue` instances.

If a required feature is absent, the strategy may choose to emit no signal.

SPEC-009 must not represent unavailable feature values as:

```text
NaN
Inf
0
```

A future orchestrator may perform required-feature readiness checks.

---

## 12. Context Lookup

Provide a small convenience method:

```python
context.get(feature_name: str, symbol: str) -> float
```

The method returns the exact available feature value.

Unknown `(feature_name, symbol)` pairs raise:

```python
KeyError
```

Do not return `None` because:

```text
missing input
```

and:

```text
feature value numerically unavailable
```

must remain distinct concepts.

Do not silently normalize lookup names or symbols.

---

## 13. Context Symbols

A derived convenience property may expose:

```python
context.symbols
```

as an immutable tuple of symbols represented in the available feature values.

The output must be deterministic.

Sorted canonical symbols are preferred.

An empty context returns:

```python
()
```

No market universe semantics are implied.

A symbol absent from this property may merely have no currently available feature values.

---

## 14. Signal

Introduce an immutable structured strategy signal.

Preferred shape:

```python
@dataclass(frozen=True, slots=True)
class Signal:
    strategy_name: str
    symbol: str
    timestamp: datetime
    score: float
```

A Signal means:

> Strategy S expresses numeric alpha score X for symbol Y as of timestamp T.

It does NOT mean:

> Execute a trade.

---

## 15. Signal Strategy Name

`strategy_name` must use the same canonical identifier rules as `StrategySpec.name`.

Do not silently normalize it.

---

## 16. Signal Symbol

`symbol` must already be canonical:

```text
non-empty
trimmed
uppercase
```

Do not silently uppercase malformed signal output.

---

## 17. Signal Timestamp

Signal timestamps must:

```text
be datetime
be timezone-aware
have utcoffset() != None
```

A correctly orchestrated strategy should emit signals for the same instant as:

```text
StrategyContext.as_of
```

The future strategy execution/orchestration layer will enforce context-output consistency when invoking arbitrary strategy implementations.

---

## 18. Signal Score

`score` must be a Python:

```python
float
```

It must be finite.

Reject:

```text
int
bool
NaN
+Inf
-Inf
```

SPEC-009 intentionally does not constrain score to:

```text
[-1, 1]
```

Different strategies may naturally produce different alpha scales.

Future portfolio construction may normalize or rank signals.

---

## 19. Signal Is Not an Order

Signal must NOT contain:

```text
quantity
shares
notional
target weight
limit price
order type
fill price
commission
slippage
cash
portfolio balance
```

Those fields belong downstream.

For example:

```python
Signal(
    strategy_name="momentum",
    symbol="AAPL",
    timestamp=t,
    score=1.42,
)
```

is valid.

This is intentionally NOT:

```text
BUY 500 AAPL
```

---

## 20. Strategy Protocol

Preferred contract:

```python
class Strategy(Protocol):
    @property
    def spec(self) -> StrategySpec:
        ...

    def generate(
        self,
        context: StrategyContext,
    ) -> tuple[Signal, ...]:
        ...
```

The returned collection must conceptually represent all signals generated at that evaluation point.

An empty tuple means:

> the strategy emits no signal at this evaluation.

---

## 21. Multiple Signals

One evaluation may produce signals for multiple symbols.

Example:

```text
AAPL +1.4
MSFT -0.3
NVDA +0.9
```

This is necessary for future:

```text
cross-sectional ranking
pairs strategies
portfolio-level alpha models
```

The Strategy protocol must therefore not be restricted to:

```python
Signal | None
```

for exactly one symbol.

---

## 22. Output Uniqueness

A conforming strategy should emit at most one signal for each symbol per evaluation.

Returning:

```text
AAPL +1.0
AAPL -0.5
```

at the same strategy evaluation is ambiguous.

SPEC-009 documents this semantic requirement.

A future strategy runner/orchestrator will enforce output consistency across arbitrary implementations.

---

## 23. Output Context Consistency

For a conforming implementation:

```text
signal.strategy_name == strategy.spec.name
signal.timestamp == context.as_of
```

for every returned signal.

SPEC-009 tests this behavior using test-only strategy implementations.

Because `Strategy` is a structural protocol, Python cannot prevent a deliberately incorrect implementation from constructing inconsistent Signals.

Future orchestration code must validate this boundary when executing untrusted/arbitrary Strategy implementations.

---

## 24. No Portfolio Access

StrategyContext must not contain:

```text
cash
positions
current portfolio weights
realized P&L
unrealized P&L
buying power
orders
fills
```

The strategy represents alpha logic only.

Portfolio construction and risk management remain separate layers.

This separation allows the same alpha strategy to be evaluated under multiple portfolio-sizing policies.

---

## 25. No Execution Access

Strategy implementations must not receive:

```text
broker
exchange
execution simulator
commission model
slippage model
order book
```

through the normal strategy API.

Therefore the same signal-generation logic can be evaluated under different execution assumptions.

---

## 26. No Historical Dataset Access

The public strategy method must not receive:

```text
complete dataset
current dataset index
Parquet store
CSV provider
DatasetCatalog
FeatureWindow history
```

The strategy receives only feature values already computed for the causal as-of boundary.

Historical information should be summarized through causal features.

---

## 27. Strategy Determinism

The intended strategy semantic contract is:

```text
same Strategy configuration
+
same StrategyContext
→
same signals
```

A strategy should not depend on:

```text
wall-clock time
network calls
filesystem state
hidden mutable global state
unseeded randomness
```

Randomized research strategies may be introduced later only with explicit seed/configuration semantics.

---

## 28. Strategy Mutation

SPEC-009 does not require strategy implementations themselves to be frozen dataclasses.

However, calling:

```python
strategy.generate(context)
```

must not mutate:

```text
StrategyContext
FeatureValue
FeatureSpec
Bar
```

Test-only implementations should demonstrate observationally pure behavior.

---

## 29. StrategySpec Runtime Contract

The protocol exposes:

```python
strategy.spec
```

which must be a valid `StrategySpec`.

A future registry/orchestrator may validate this at runtime.

SPEC-009 does not introduce a strategy registry.

---

## 30. Module Structure

Preferred:

```text
src/quantforge/strategies/
    __init__.py
    base.py
```

Preferred public API:

```python
from quantforge.strategies import (
    Signal,
    Strategy,
    StrategyContext,
    StrategySpec,
)
```

Do not introduce concrete production strategies.

---

## 31. Dependencies

Use only:

```text
Python standard library
existing FeatureValue domain model
```

No new runtime dependency.

Do not add:

```text
NumPy
Pandas
SciPy
scikit-learn
Polars
```

---

## 32. Validation Errors

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

Examples:

```text
StrategySpec name=123             → TypeError
StrategySpec name=" Momentum "    → ValueError
required_features as list         → TypeError
duplicate required feature names  → ValueError

StrategyContext naive as_of       → ValueError
features as list                  → TypeError
duplicate feature/symbol pair     → ValueError
mixed feature timestamps          → ValueError

Signal symbol=" aapl "            → ValueError
Signal score=1                    → TypeError
Signal score=NaN                  → ValueError
```

Do not silently repair malformed strategy-domain objects.

---

## 33. Time-Safety Boundary

SPEC-009 builds on SPEC-007.

The causal chain is intended to be:

```text
historical Bars through t
        ↓
FeatureWindow ending at t
        ↓
FeatureValue timestamped t
        ↓
StrategyContext as_of=t
        ↓
Signal timestamped t
```

No normal strategy API exposes:

```text
t + 1
```

information.

This does not technically prevent malicious strategy code from opening external files.

It minimizes accidental look-ahead through the supported architecture.

---

## 34. Cross-Sectional Readiness

Unlike FeatureWindow, StrategyContext may contain multiple symbols.

This is intentional.

Feature calculation remains:

```text
single-symbol causal window
```

while strategy evaluation may operate on:

```text
multiple symbols at one common as-of time
```

This supports future research such as:

```text
cross-sectional momentum
relative-value ranking
pairs trading
multi-asset allocation signals
ML scoring across a universe
```

without changing the core strategy interface.

---

## 35. Test-Only Example

A test-only strategy may conceptually be:

```python
class PositiveMomentumStrategy:
    @property
    def spec(self) -> StrategySpec:
        return StrategySpec(
            name="positive_momentum",
            required_features=("momentum_20",),
        )

    def generate(
        self,
        context: StrategyContext,
    ) -> tuple[Signal, ...]:
        signals = []

        for symbol in context.symbols:
            try:
                momentum = context.get("momentum_20", symbol)
            except KeyError:
                continue

            signals.append(
                Signal(
                    strategy_name=self.spec.name,
                    symbol=symbol,
                    timestamp=context.as_of,
                    score=momentum,
                )
            )

        return tuple(signals)
```

This exists only for tests/documentation.

Do not ship it as a production financial strategy in SPEC-009.

---

## 36. Tests

Tests must cover at least the following domains.

StrategySpec:

```text
valid canonical name
invalid empty name
surrounding whitespace
uppercase name
wrong name type
empty required feature tuple
multiple required features
duplicate required feature names
list instead of tuple
invalid feature name
immutability
hashability
```

StrategyContext:

```text
empty features
single symbol
multiple symbols
multiple features
tuple requirement
non-FeatureValue element
timezone-aware as_of
naive as_of rejection
feature timestamps matching as_of
feature timestamp before as_of rejected
feature timestamp after as_of rejected
same instant with equivalent timezone offset accepted
duplicate (feature_name, symbol) rejected
deterministic symbols property
exact lookup
unknown lookup raises KeyError
lookup does not normalize names/symbols
immutability
hashability when naturally supported
```

Signal:

```text
valid positive score
negative score
zero score
non-float rejected
bool rejected
NaN rejected
infinities rejected
canonical strategy name
canonical symbol
naive timestamp rejected
immutability
hashability
```

Protocol:

```text
test-only strategy conforms under strict mypy
strategy receives StrategyContext
strategy emits tuple[Signal, ...]
empty signal output supported
multiple-symbol signal output supported
repeated deterministic invocation
input context remains unchanged
```

Architecture semantics:

```text
Signal contains no quantity/order/fill fields
StrategyContext exposes no portfolio state
StrategyContext exposes no complete dataset/index
```

---

## 37. Acceptance Criteria

* [x] strategies package exists.
* [x] `StrategySpec` exists and is immutable.
* [x] strategy names use canonical identifiers.
* [x] required feature names are immutable.
* [x] duplicate required features are rejected.
* [x] required feature declaration order is preserved.
* [x] `StrategyContext` exists and is immutable.
* [x] context `as_of` is timezone-aware.
* [x] context features are an immutable tuple.
* [x] context contains only `FeatureValue`.
* [x] all context feature timestamps match the context as-of instant.
* [x] duplicate `(feature_name, symbol)` inputs are rejected.
* [x] empty contexts are supported.
* [x] multiple symbols are supported.
* [x] context lookup works.
* [x] missing context feature lookup raises `KeyError`.
* [x] lookup does not silently normalize input.
* [x] deterministic symbol enumeration is available.
* [x] `Signal` exists and is immutable.
* [x] signal strategy name is canonical.
* [x] signal symbol must already be canonical.
* [x] signal timestamp is timezone-aware.
* [x] signal score is a Python float.
* [x] signal score must be finite.
* [x] positive, negative, and zero scores are supported.
* [x] score range is not artificially restricted to [-1, 1].
* [x] Signal contains no order quantity.
* [x] Signal contains no target portfolio weight.
* [x] Signal contains no execution price.
* [x] Signal contains no commission/slippage fields.
* [x] `Strategy` protocol exists.
* [x] protocol exposes immutable strategy metadata through `spec`.
* [x] protocol receives only `StrategyContext`.
* [x] protocol returns `tuple[Signal, ...]`.
* [x] multiple-symbol output is supported.
* [x] empty output is supported.
* [x] no portfolio object is passed to strategy.
* [x] no cash/position state is passed to strategy.
* [x] no order or execution object is passed to strategy.
* [x] no complete historical dataset/index is passed to strategy.
* [x] test-only implementation demonstrates context/signal timestamp consistency.
* [x] test-only implementation demonstrates strategy-name consistency.
* [x] deterministic repeated strategy evaluation is tested.
* [x] input context remains unchanged.
* [x] no concrete production trading strategy is introduced.
* [x] no strategy registry is introduced.
* [x] no feature engine is introduced.
* [x] no portfolio construction is introduced.
* [x] no order domain model is introduced.
* [x] no runtime dependency is introduced.
* [x] pytest passes.
* [x] Ruff lint passes.
* [x] Ruff formatting passes.
* [x] strict mypy passes.
* [x] `git diff --check` passes.
* [x] specification index is updated.
* [x] architecture documentation reflects only implemented behavior.
* [x] meaningful decisions or bugs are recorded.

---

## 38. Performance Considerations

SPEC-009 prioritizes clear semantics over performance optimization.

StrategyContext may perform linear construction-time validation across its feature values.

A simple lookup implementation may construct or derive mappings as appropriate, but avoid unnecessary mutable state or premature indexing abstractions.

Future profiling can justify optimized context representations.

Do not weaken causal or immutability guarantees for hypothetical performance requirements.

---

## 39. Engineering Decision Expected

Record the next appropriate engineering decision describing why QuantForge separates:

```text
alpha Signal
from
Portfolio sizing
from
Order generation
from
Execution
```

and why StrategyContext permits multiple symbols at one common as-of time while withholding portfolio and execution state.

---

## 40. Dependencies

Depends on:

```text
SPEC-007 — Feature Interface
SPEC-008 — Feature Registry & Cache conceptually
```

No new runtime dependencies.

Expected next specification:

```text
SPEC-010 — Portfolio State & Accounting
```

Do not begin SPEC-010 during SPEC-009 implementation.

---

## 41. Completion Summary

Status: Completed

Files created:

* `src/quantforge/strategies/__init__.py`
* `src/quantforge/strategies/base.py`
* `tests/test_strategy_interface.py`
* `docs/specs/SPEC-009-strategy-interface.md`

Files modified:

* `ARCHITECTURE.md`
* `docs/ENGINEERING_LOG.md`
* `docs/specs/INDEX.md`

Public API:

* `quantforge.strategies.StrategySpec`
* `quantforge.strategies.StrategyContext`
* `quantforge.strategies.Signal`
* `quantforge.strategies.Strategy`

StrategyContext behavior:

* A context contains only an explicit timezone-aware `as_of` and an immutable tuple of available
  `FeatureValue` objects, potentially across multiple symbols.
* Every feature timestamp must equal the context as-of instant, including equality across equivalent
  timezone offsets, and duplicate `(feature_name, symbol)` pairs are rejected.
* `get(feature_name, symbol)` performs exact lookup and raises `KeyError` for absence; `symbols`
  returns a deterministic sorted tuple.

Signal semantics:

* A signal contains only canonical strategy identity, canonical symbol, timezone-aware timestamp,
  and an unrestricted finite float alpha score.
* Signals carry no quantity, portfolio, order, fill, commission, slippage, or execution semantics.
* The protocol returns `tuple[Signal, ...]`, including empty and multi-symbol outputs.

Tests added:

* 65 deterministic cases cover specification metadata, context timestamp/input invariants, exact
  lookup, multi-symbol readiness, signal validation and boundary fields, protocol conformance,
  empty/multiple outputs, deterministic generation, and input immutability.

Commands run:

* `.venv/bin/python -m pytest` — 337 passed.
* `.venv/bin/python -m ruff check .` — passed.
* `.venv/bin/python -m ruff format --check .` — passed.
* `.venv/bin/python -m mypy src tests` — passed in strict mode.
* `git diff --check` — passed.

Known limitations:

* No production trading strategy or invocation orchestrator is implemented.
* A future orchestrator must validate arbitrary outputs, including strategy name, context timestamp,
  and per-symbol uniqueness.
* The supported API reduces accidental future-data access but cannot prevent malicious strategy code
  from reaching external state independently.
* Required-feature readiness, strategy registration, portfolio sizing, orders, and execution remain
  intentionally unavailable.

Engineering log entries:

* `DECISION-011 — Separate Alpha Signals from Portfolio and Execution Decisions`

Follow-up specifications:

* SPEC-010 may define portfolio state and accounting without moving sizing or execution fields into
  `Signal`.

Expected next specification:

`SPEC-010 — Portfolio State & Accounting`
