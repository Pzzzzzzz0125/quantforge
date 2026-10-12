# SPEC-010 — Portfolio State & Accounting

Status: Completed
Owner: Paul
Created: 2026-09-11
Updated: 2026-09-11

## 1. Problem

QuantForge can produce structured alpha `Signal` objects, but it does not yet have a financially correct representation of portfolio state.

Future execution and backtesting layers will need a deterministic accounting boundary that can answer:

* how cash changes after an executed trade;
* how signed position quantity changes;
* how average cost changes;
* how realized P&L changes when positions are reduced or closed;
* how long positions reverse into short positions;
* how short positions reverse into long positions;
* how transaction fees affect cash and total P&L;
* how current market prices produce unrealized P&L and portfolio equity.

These rules must be independent of strategy logic, order generation, execution simulation, commission calculation, and slippage modeling.

---

## 2. Goal

Implement immutable portfolio-accounting domain objects and pure state transitions.

SPEC-010 must introduce:

* `PositionState`
* `PortfolioState`
* `PortfolioValuation`

The accounting layer receives already-executed trade facts through a small state-transition API.

It does not decide whether the trade should have occurred.

---

## 3. Core Architecture

The intended future flow is:

```text
Signal
  ↓
Portfolio Construction
  ↓
Order
  ↓
Execution
  ↓
Fill
  ↓
Portfolio Accounting
  ↓
new PortfolioState
```

SPEC-010 implements only the accounting layer.

Until a `Fill` domain object is introduced in a later specification, accounting may receive the minimal executed-trade facts directly:

```text
symbol
signed quantity
execution price
fee
```

This does not define execution behavior.

---

## 4. Non-Goals

SPEC-010 does NOT implement:

* portfolio construction;
* signal sizing;
* target weights;
* risk limits;
* buying-power checks;
* margin requirements;
* order objects;
* fill objects;
* order matching;
* market orders;
* limit orders;
* partial-fill simulation;
* commission models;
* slippage models;
* event systems;
* backtest loops;
* market-data fetching;
* trading calendars;
* dividends;
* stock splits;
* corporate actions;
* borrow fees;
* financing interest;
* cash deposits or withdrawals;
* multiple currencies;
* tax accounting;
* lot-selection methods such as FIFO/LIFO.

Those concerns belong to later specifications.

---

## 5. Accounting Convention

Position quantity is signed.

```text
quantity > 0   long
quantity < 0   short
quantity = 0   flat
```

Executed trade quantity is also signed.

```text
fill quantity > 0   buy
fill quantity < 0   sell
```

Examples:

```text
current position 0
fill +100
→ long 100

current position +100
fill -40
→ long 60

current position +100
fill -150
→ short 50

current position -100
fill +40
→ short 60

current position -100
fill +150
→ long 50
```

This convention must be documented and tested explicitly.

---

## 6. Quantity Type

QuantForge's initial equity accounting model uses integer share quantities.

Therefore:

```text
PositionState.quantity
```

must be a Python `int`.

Booleans must be rejected.

Executed fill quantities must also be Python integers.

A fill quantity of zero is invalid because it represents no execution.

Fractional-share accounting may be introduced later if required.

---

## 7. Price Type

Accounting prices use Python `float`, consistent with canonical market-bar prices.

Execution price must:

* be a Python float;
* be finite;
* be strictly greater than zero.

Reject:

```text
int
bool
NaN
+Inf
-Inf
0.0
negative prices
```

The accounting layer never silently rounds or repairs prices.

---

## 8. Fee Semantics

Accounting accepts an explicit:

```python
fee: float
```

representing the total transaction fee already determined by an upstream execution/commission layer.

The fee must:

* be a Python float;
* be finite;
* be greater than or equal to zero.

SPEC-010 does not calculate the fee.

Future commission models will calculate it and pass the resulting amount into accounting.

A fee always reduces cash.

---

## 9. PositionState

Introduce an immutable position state.

Preferred shape:

```python
@dataclass(frozen=True, slots=True)
class PositionState:
    symbol: str
    quantity: int
    average_cost: float | None
    realized_pnl: float
```

`realized_pnl` means cumulative **gross realized trading P&L**, excluding transaction fees.

Fees are tracked separately by `PortfolioState`.

---

## 10. Position Symbol

`symbol` must already be canonical:

```text
non-empty
trimmed
uppercase
```

Do not silently normalize malformed symbols.

---

## 11. Position Quantity

`quantity` may be:

```text
positive
negative
zero
```

Zero represents a flat position.

---

## 12. Average Cost

For an open position:

```text
quantity != 0
```

`average_cost` must be:

* Python float;
* finite;
* strictly positive.

For a flat position:

```text
quantity == 0
```

`average_cost` must be:

```python
None
```

This invariant must always hold.

---

## 13. Realized P&L

`realized_pnl` must:

* be a Python float;
* be finite.

It may be:

```text
positive
negative
zero
```

Closing profitable exposure increases realized P&L.

Closing losing exposure decreases realized P&L.

Opening exposure alone does not create gross realized trading P&L.

---

## 14. Average Cost — Increasing Exposure

Suppose the existing and incoming quantities have the same sign.

Existing:

```text
quantity = q0
average cost = c0
```

Incoming:

```text
quantity = qf
execution price = p
```

where:

```text
sign(q0) == sign(qf)
```

The new average cost is:

```text
new_average_cost =
(
    abs(q0) * c0
    +
    abs(qf) * p
)
/
abs(q0 + qf)
```

Example:

```text
buy 100 @ 50
buy 100 @ 60
```

results in:

```text
quantity = 200
average_cost = 55
```

The same weighted-average rule applies when increasing a short position.

---

## 15. Reducing a Long Position

Existing:

```text
+100 shares
average cost = 50
```

Sell:

```text
-40 shares @ 60
```

Closed quantity:

```text
40
```

Gross realized P&L:

```text
40 × (60 - 50) = +400
```

Remaining:

```text
+60 shares
average cost remains 50
```

A partial close must never change the average cost of the remaining original exposure.

---

## 16. Reducing a Short Position

Existing:

```text
-100 shares
average cost = 50
```

Buy to cover:

```text
+40 shares @ 40
```

Gross realized P&L:

```text
40 × (50 - 40) = +400
```

Remaining:

```text
-60 shares
average cost remains 50
```

---

## 17. Unified Realized P&L Rule

When the incoming trade is opposite the existing position direction:

```text
closed_quantity =
min(abs(existing_quantity), abs(fill_quantity))
```

The realized P&L delta may be represented conceptually as:

```text
closed_quantity
×
(execution_price - existing_average_cost)
×
sign(existing_quantity)
```

Therefore:

```text
long:
sign = +1
profit when execution price > average cost

short:
sign = -1
profit when execution price < average cost
```

---

## 18. Full Close

If:

```text
abs(fill_quantity) == abs(existing_quantity)
```

and directions are opposite:

```text
new quantity = 0
new average cost = None
```

The realized P&L from the entire closed exposure is accumulated.

---

## 19. Position Reversal

A single execution may cross through zero.

Example:

```text
existing:
+100 @ 50

execution:
sell 150 @ 60
```

Accounting must treat this as:

```text
close long 100 @ 60
+
open short 50 @ 60
```

Result:

```text
quantity = -50
average_cost = 60
realized P&L delta = +1000
```

The residual reversed position receives the current execution price as its new average cost.

Likewise:

```text
existing short
+
buy larger quantity
```

may reverse into a long position.

---

## 20. Cash Accounting

For signed execution quantity:

```text
q
```

execution price:

```text
p
```

and transaction fee:

```text
f
```

cash changes by:

```text
cash_delta = -(q × p) - f
```

Therefore:

Buy:

```text
q > 0
→ cash decreases
```

Sell:

```text
q < 0
→ cash increases
```

Fee:

```text
always decreases cash
```

Example:

```text
cash = 100,000
buy 100 @ 50
fee = 2
```

results in:

```text
cash = 94,998
```

---

## 21. PortfolioState

Introduce an immutable portfolio snapshot.

Preferred shape:

```python
@dataclass(frozen=True, slots=True)
class PortfolioState:
    initial_cash: float
    cash: float
    positions: tuple[PositionState, ...]
    fees_paid: float
```

The state is a snapshot.

Applying an execution returns a **new** `PortfolioState`.

The previous state remains unchanged.

---

## 22. Starting Portfolio

Provide a convenience constructor such as:

```python
PortfolioState.starting(initial_cash=100_000.0)
```

which creates:

```text
initial_cash = 100000
cash = 100000
positions = ()
fees_paid = 0
```

`initial_cash` must be a finite Python float.

For SPEC-010 it must be greater than or equal to zero.

---

## 23. Cash State

`PortfolioState.cash` must be finite.

Unlike `initial_cash`, current cash may become negative.

Accounting does not enforce:

```text
buying power
margin
leverage limits
risk constraints
```

Those belong upstream.

Therefore a transaction that creates negative cash may still be accounted for correctly.

---

## 24. Fees Paid

`fees_paid` represents cumulative transaction fees.

It must:

* be a finite Python float;
* be greater than or equal to zero.

Every accounting transition adds the execution's fee.

---

## 25. Portfolio Position Collection

`positions` must:

* be a tuple;
* contain only `PositionState`;
* contain no duplicate symbols;
* have deterministic ordering.

Sorted symbol order is preferred.

Flat positions may remain in the state to preserve their cumulative realized-P&L history.

---

## 26. Position Lookup

Provide:

```python
state.get_position(symbol: str) -> PositionState | None
```

Lookup must be exact.

Do not silently uppercase or trim symbols.

If the symbol has never appeared in portfolio state:

```python
None
```

is returned.

This is not an error.

---

## 27. Active Positions

A convenience property may expose:

```python
state.active_positions
```

as an immutable tuple containing only:

```text
quantity != 0
```

positions.

Ordering must remain deterministic.

---

## 28. Gross Realized P&L

Provide a derived portfolio property:

```python
state.gross_realized_pnl
```

equal to the sum of:

```text
PositionState.realized_pnl
```

across all position records.

Transaction fees are not included in this value.

---

## 29. Applying an Executed Trade

Preferred API:

```python
new_state = state.apply_fill(
    symbol="AAPL",
    quantity=100,
    price=50.0,
    fee=1.0,
)
```

This API records accounting facts only.

It does not imply that SPEC-010 defines the future `Fill` domain object.

Requirements:

* symbol canonical;
* quantity nonzero integer;
* price valid positive finite float;
* fee valid nonnegative finite float;
* transition deterministic;
* original state unchanged.

---

## 30. No Execution Simulation

`apply_fill()` must NOT decide:

```text
whether order fills
how much order fills
at what simulated price
what slippage applies
what commission model applies
```

Those values are assumed to have already been determined.

This method merely accounts for them.

---

## 31. PortfolioValuation

Introduce an immutable valuation result.

Preferred shape:

```python
@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    initial_cash: float
    cash: float
    market_value: float
    equity: float
    gross_realized_pnl: float
    unrealized_pnl: float
    fees_paid: float
    total_pnl: float
```

---

## 32. Mark-to-Market API

Preferred:

```python
valuation = state.value(
    {
        "AAPL": 62.0,
        "MSFT": 405.0,
    }
)
```

Input type:

```python
Mapping[str, float]
```

Each mark actually required for an open position must:

* be a Python float;
* be finite;
* be strictly positive.

Integers, booleans, NaN, infinity, zero, and negative marks are rejected.

---

## 33. Required Marks

Every nonzero position requires a mark.

Missing mark:

```python
KeyError
```

A flat historical position does not require a mark.

Extra marks for symbols not currently held may be ignored.

No silent symbol normalization is permitted.

---

## 34. Position Market Value

For each open position:

```text
market_value =
quantity × mark_price
```

Long position market value is positive.

Short position market value is negative.

Portfolio market value is the sum across open positions.

---

## 35. Portfolio Equity

Portfolio equity is:

```text
equity =
cash
+
market value of all open positions
```

This invariant is fundamental.

---

## 36. Unrealized P&L

For every nonzero position:

```text
unrealized_pnl =
quantity
×
(mark_price - average_cost)
```

Because quantity is signed, this formula naturally supports long and short positions.

Example long:

```text
+100
average cost 50
mark 60

unrealized = +1000
```

Example short:

```text
-100
average cost 50
mark 40

unrealized = +1000
```

---

## 37. Total P&L

Because SPEC-010 does not support deposits or withdrawals:

```text
total_pnl =
equity - initial_cash
```

This includes transaction fees through cash accounting.

A second reconciliation identity must hold:

```text
total_pnl
≈
gross_realized_pnl
+
unrealized_pnl
-
fees_paid
```

Approximate floating-point comparison is acceptable in tests.

This is one of the central accounting invariants.

---

## 38. Fee Separation

Gross realized P&L excludes fees.

Example:

```text
buy 100 @ 50, fee 2
sell 100 @ 60, fee 2
```

Gross realized trading P&L:

```text
1000
```

Fees paid:

```text
4
```

Net total P&L:

```text
996
```

This separation allows later analytics to report:

```text
gross trading P&L
transaction costs
net P&L
```

independently.

---

## 39. Zero-Cost Round Trip

One mandatory accounting regression test:

```text
initial cash = 100000

buy 100 @ 50
fee = 0

sell 100 @ 50
fee = 0
```

Final state must satisfy:

```text
cash = 100000
quantity = 0
average cost = None
gross realized P&L = 0
fees = 0
equity = 100000
total P&L = 0
```

Any violation indicates an accounting defect.

---

## 40. Profitable Long Round Trip

Example:

```text
initial = 100000

buy 100 @ 50
sell 100 @ 60
```

Expected:

```text
cash = 101000
position = flat
gross realized P&L = +1000
equity = 101000
total P&L = +1000
```

---

## 41. Losing Long Round Trip

Example:

```text
buy 100 @ 50
sell 100 @ 40
```

Expected gross realized P&L:

```text
-1000
```

---

## 42. Profitable Short Round Trip

Example:

```text
sell short 100 @ 50
buy to cover 100 @ 40
```

Expected gross realized P&L:

```text
+1000
```

The accounting layer must support this without special-case portfolio hacks.

---

## 43. Losing Short Round Trip

Example:

```text
sell short 100 @ 50
buy to cover 100 @ 60
```

Expected gross realized P&L:

```text
-1000
```

---

## 44. Immutability

The following must be immutable:

```text
PositionState
PortfolioState
PortfolioValuation
```

Preferred:

```python
@dataclass(frozen=True, slots=True)
```

Applying accounting transitions creates new snapshots.

This makes event replay and regression testing easier.

---

## 45. Determinism

Given:

```text
same PortfolioState
+
same execution facts
```

the resulting state must be identical.

No accounting calculation may depend on:

```text
wall clock
network
filesystem
randomness
hidden global state
```

---

## 46. Error Handling

Use:

```text
TypeError
```

for fundamentally incorrect Python types.

Use:

```text
ValueError
```

for invalid values.

Examples:

```text
quantity=True          → TypeError
quantity=1.5           → TypeError
quantity=0             → ValueError

price=50               → TypeError
price=0.0              → ValueError
price=NaN              → ValueError

fee=1                  → TypeError
fee=-1.0               → ValueError

noncanonical symbol    → ValueError
```

Do not silently repair malformed accounting input.

---

## 47. Tests — Position Domain

Tests must cover at least:

```text
long PositionState
short PositionState
flat PositionState
flat requires average_cost=None
open requires average_cost
invalid canonical symbol
invalid quantity type
invalid average cost
nonfinite realized P&L
immutability
```

---

## 48. Tests — Long Accounting

Cover:

```text
open long
increase long
weighted average cost
partial profitable close
partial losing close
full profitable close
full losing close
average cost unchanged after partial close
long → short reversal
```

---

## 49. Tests — Short Accounting

Cover:

```text
open short
increase short
weighted short average cost
partial profitable cover
partial losing cover
full profitable cover
full losing cover
average cost unchanged after partial cover
short → long reversal
```

---

## 50. Tests — Cash and Fees

Cover:

```text
buy decreases cash
sell increases cash
short sale increases cash
cover decreases cash
fee always decreases cash
fees accumulate
negative cash is permitted
fee does not change gross realized trading P&L
```

---

## 51. Tests — Valuation

Cover:

```text
cash-only portfolio
one long
one short
mixed long + short
market value
equity
unrealized P&L
gross realized P&L
fees
total P&L
accounting reconciliation identity
missing mark
extra mark
invalid mark type/value
flat position requires no mark
```

---

## 52. Tests — State Transition

Cover:

```text
original state unchanged
new state returned
position collection deterministic
no duplicate position symbols
position lookup
active positions
repeated deterministic transition
```

---

## 53. Mandatory Hand-Calculated Scenarios

Tests must explicitly include:

### Scenario A

```text
Initial cash: 100000
Buy 100 @ 50
Mark: 50
```

Expected:

```text
cash = 95000
market value = 5000
equity = 100000
unrealized P&L = 0
```

### Scenario B

```text
Initial cash: 100000
Buy 100 @ 50
Mark: 60
```

Expected:

```text
cash = 95000
market value = 6000
equity = 101000
unrealized P&L = 1000
```

### Scenario C

```text
Initial cash: 100000
Short 100 @ 50
Mark: 40
```

Expected:

```text
cash = 105000
market value = -4000
equity = 101000
unrealized P&L = 1000
```

### Scenario D

```text
Buy 100 @ 50
Buy 100 @ 60
```

Expected:

```text
quantity = 200
average cost = 55
```

### Scenario E

```text
Long 100 @ 50
Sell 150 @ 60
```

Expected:

```text
quantity = -50
average cost = 60
gross realized P&L = 1000
```

---

## 54. Architecture Boundary Tests

Tests or structural assertions should demonstrate that SPEC-010 introduces no:

```text
Order
OrderType
Signal dependency
Strategy dependency
ExecutionSimulator
CommissionModel
SlippageModel
EventLoop
```

Portfolio accounting should remain independently testable.

---

## 55. Public Module

Preferred:

```text
src/quantforge/portfolio/
    __init__.py
    accounting.py
```

Preferred public imports:

```python
from quantforge.portfolio import (
    PortfolioState,
    PortfolioValuation,
    PositionState,
)
```

---

## 56. Dependency Policy

No new runtime dependency.

Use only:

```text
Python standard library
existing QuantForge conventions
```

Do not add:

```text
NumPy
Pandas
Decimal third-party packages
accounting libraries
```

---

## 57. Floating-Point Policy

SPEC-010 uses Python float because the existing QuantForge price domain uses Python float.

Tests involving arithmetic reconciliation should use appropriate approximate comparison where binary floating-point representation may differ by tiny amounts.

Do not hide meaningful accounting discrepancies behind overly loose tolerances.

Correctness tolerances should be narrow.

---

## 58. Performance

Portfolio updates may initially rebuild immutable position tuples.

This is acceptable.

Correct accounting semantics are more important than optimizing portfolio updates before profiling.

Future performance work may introduce more efficient internal state while preserving identical accounting behavior.

---

## 59. Known Initial Limitations

SPEC-010 intentionally supports:

```text
single currency
integer-share equities
average-cost accounting
long and short positions
explicit externally supplied fees
```

It does not yet support:

```text
fractional shares
multiple currencies
tax lots
FIFO/LIFO
margin rules
corporate actions
borrow costs
interest
dividends
cash flows
```

These limitations must be documented rather than silently approximated.

---

## 60. Engineering Decision Expected

Record the next engineering decision describing why QuantForge uses:

```text
immutable portfolio snapshots
+
signed quantities
+
average-cost position accounting
+
gross realized P&L separated from fees
```

and why accounting accepts executed trade facts without owning order/execution logic.

---

## 61. Acceptance Criteria

* [x] portfolio package exists.
* [x] `PositionState` exists and is immutable.
* [x] `PortfolioState` exists and is immutable.
* [x] `PortfolioValuation` exists and is immutable.
* [x] signed position quantity convention is implemented.
* [x] integer share quantities are enforced.
* [x] booleans are rejected as quantities.
* [x] canonical symbols are enforced.
* [x] open positions require positive finite average cost.
* [x] flat positions require `average_cost=None`.
* [x] realized P&L is finite.
* [x] starting portfolio constructor exists.
* [x] initial cash is validated.
* [x] current cash may become negative.
* [x] fees are explicit finite nonnegative floats.
* [x] position lookup works.
* [x] active positions are available deterministically.
* [x] gross realized P&L is derived correctly.
* [x] executed trade application returns a new state.
* [x] original state remains unchanged.
* [x] buy reduces cash.
* [x] sell increases cash.
* [x] fees always reduce cash.
* [x] long opening works.
* [x] long increase uses weighted average cost.
* [x] long partial close works.
* [x] long full close works.
* [x] long realized profit is correct.
* [x] long realized loss is correct.
* [x] long-to-short reversal works.
* [x] short opening works.
* [x] short increase uses weighted average cost.
* [x] short partial cover works.
* [x] short full cover works.
* [x] short realized profit is correct.
* [x] short realized loss is correct.
* [x] short-to-long reversal works.
* [x] partial reduction preserves prior average cost.
* [x] reversal residual uses execution price as new average cost.
* [x] portfolio valuation accepts explicit marks.
* [x] all open positions require marks.
* [x] flat positions do not require marks.
* [x] market value is correct.
* [x] equity equals cash plus signed position market value.
* [x] unrealized P&L supports long positions.
* [x] unrealized P&L supports short positions.
* [x] total P&L equals equity minus initial cash.
* [x] total P&L reconciles with realized + unrealized - fees.
* [x] zero-cost equal-price round trip preserves equity.
* [x] profitable long round trip is correct.
* [x] profitable short round trip is correct.
* [x] fee accounting is separated from gross realized P&L.
* [x] no order model is implemented.
* [x] no execution simulator is implemented.
* [x] no commission/slippage model is implemented.
* [x] no runtime dependency is introduced.
* [x] pytest passes.
* [x] Ruff lint passes.
* [x] Ruff formatting passes.
* [x] strict mypy passes.
* [x] `git diff --check` passes.
* [x] specification index is updated.
* [x] architecture documentation reflects only implemented behavior.
* [x] meaningful decisions and bugs are recorded.

---

## 62. Dependencies

Depends conceptually on future execution integration but requires no future module to implement.

Existing runtime dependencies introduced by earlier specifications remain unchanged.

New runtime dependencies:

```text
none
```

Expected next specification:

```text
SPEC-011 — Order Domain Model
```

Do not begin SPEC-011 during this implementation.

---

## 63. Completion Summary

Status: Completed

Files created:

* `src/quantforge/portfolio/__init__.py`
* `src/quantforge/portfolio/accounting.py`
* `tests/test_portfolio_accounting.py`
* `docs/specs/SPEC-010-portfolio-accounting.md`

Files modified:

* `ARCHITECTURE.md`
* `docs/ENGINEERING_LOG.md`
* `docs/specs/INDEX.md`

Public API:

* `quantforge.portfolio.PositionState`
* `quantforge.portfolio.PortfolioState`
* `quantforge.portfolio.PortfolioValuation`

Accounting convention:

* Position and executed quantities are signed integers: positive means long/buy, negative means
  short/sell, and zero position quantity means flat.
* Cash changes by exactly `-(quantity * price) - fee`; externally supplied fees accumulate
  separately from gross realized trading P&L.

Long accounting:

* Same-direction buys use absolute-quantity weighted average cost.
* Partial sales preserve average cost, while full sales set `average_cost=None` and accumulate
  `closed_quantity * (price - average_cost)`.

Short accounting:

* Same-direction short sales use the same absolute-quantity weighted average cost rule.
* Partial covers preserve average cost, while full covers accumulate
  `closed_quantity * (price - average_cost) * -1` and become flat.

Reversal behavior:

* A crossing trade closes the entire existing exposure, realizes P&L using its signed direction,
  and assigns the current execution price as the residual reversed position's average cost.

Valuation behavior:

* Open positions require exact canonical marks; flat historical positions do not.
* Signed market value is `quantity * mark`, signed unrealized P&L is
  `quantity * (mark - average_cost)`, equity is `cash + market_value`, and total P&L is
  `equity - initial_cash`.
* `PortfolioValuation` enforces narrow-tolerance reconciliation with
  `gross_realized_pnl + unrealized_pnl - fees_paid`.

Tests added:

* 100 deterministic cases cover domain validation, immutable transitions, long/short opens and
  increases, weighted averages, partial/full closes, both reversal directions, cash and fees,
  signed valuation, required marks, and all accounting identities.
* Hand-calculated scenarios cover long marks at and above cost, profitable short valuation,
  weighted averaging, profitable/loss-making closes, fees, reversals, and the zero-cost equal-price
  round trip.

Commands run:

* `.venv/bin/python -m pytest` — 437 passed.
* `.venv/bin/python -m ruff check .` — passed.
* `.venv/bin/python -m ruff format --check .` — passed.
* `.venv/bin/python -m mypy src tests` — passed in strict mode.
* `git diff --check` — passed.

Known limitations:

* Accounting supports one currency, integer shares, average cost, long/short exposure, and explicit
  caller-supplied fees only.
* Fractional shares, tax lots, FIFO/LIFO, margin, leverage, financing, borrow costs, dividends,
  corporate actions, cash flows, orders, execution, and backtesting are not implemented.

Engineering log entries:

* `DECISION-012 — Use Immutable Signed Average-Cost Portfolio Accounting`

Expected next specification:

`SPEC-011 — Order Domain Model`
