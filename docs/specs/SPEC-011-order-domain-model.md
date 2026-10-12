# SPEC-011 — Order Domain Model

Status: Completed  
Owner: Paul  
Created: 2026-09-12  
Updated: 2026-09-12

## 1. Problem

QuantForge now has:

- causal strategy signals;
- immutable portfolio accounting;
- correct long/short position state transitions.

The system still lacks a structured representation of trading intent between future portfolio construction and future execution simulation.

Without an order-domain contract, downstream components could inconsistently represent:

- buy versus sell intent;
- requested quantity;
- market versus limit behavior;
- order identity;
- submission time;
- limit-price requirements.

QuantForge therefore needs a small immutable Order domain model.

---

## 2. Goal

Introduce:

- `OrderSide`
- `OrderType`
- `Order`

The Order model represents execution intent only.

It must not represent:

- execution outcome;
- fill quantity;
- fill price;
- portfolio state;
- transaction cost;
- strategy score.

---

## 3. Architecture Boundary

The intended pipeline is:

```text
Strategy
    ↓
Signal
    ↓
Portfolio Construction
    ↓
Order
    ↓
Execution Simulator
    ↓
Fill
    ↓
Portfolio Accounting
```

SPEC-011 implements only:

```text
Order
```

It does not implement the surrounding orchestration.

---

## 4. Non-Goals

SPEC-011 does NOT implement:

- portfolio construction;
- signal-to-order conversion;
- order manager;
- execution simulator;
- matching engine;
- fill model;
- partial fills;
- order status;
- cancellation;
- amendment;
- rejected orders;
- commission;
- slippage;
- market impact;
- order book;
- event system;
- backtest loop;
- time-in-force;
- stop orders;
- stop-limit orders;
- trailing stops;
- bracket orders;
- buying-power validation;
- risk management.

Those belong to later specifications.

---

## 5. OrderSide

Introduce:

```python
class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"
```

The side is explicit.

Order quantity itself is always positive.

Therefore:

```text
BUY 100
```

means purchase 100 shares.

```text
SELL 100
```

means sell 100 shares.

Do not encode SELL through negative order quantity.

---

## 6. Why Order Quantity Is Unsigned

SPEC-010 uses signed quantities internally for accounting:

```text
+100 = buy / long increase
-100 = sell / short increase
```

SPEC-011 intentionally uses:

```text
side + positive quantity
```

because this is clearer at the execution-intent boundary.

A future Fill may translate:

```text
BUY 100  → accounting quantity +100
SELL 100 → accounting quantity -100
```

This keeps human-facing order semantics explicit while retaining the signed accounting model internally.

---

## 7. OrderType

Introduce:

```python
class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
```

No other order type is introduced in SPEC-011.

---

## 8. Order

Preferred shape:

```python
@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    timestamp: datetime
    limit_price: float | None = None
```

The object must be immutable and naturally hashable.

---

## 9. Order ID

`order_id` is an opaque stable identifier.

Requirements:

- Python `str`;
- non-empty;
- no surrounding whitespace.

The domain object must NOT automatically generate its own UUID.

Order-ID generation belongs to a future orchestration/order-management layer.

This keeps domain construction deterministic and replay-friendly.

Examples:

```text
order_001
run42_order_17
abc123
```

SPEC-011 does not impose UUID syntax.

---

## 10. Order ID Uniqueness

An individual `Order` cannot know whether another order uses the same ID.

Therefore SPEC-011 validates only that the identifier is structurally valid.

Global uniqueness belongs to a future:

```text
OrderManager / Backtest Engine
```

Do not introduce global registries or hidden mutable ID state.

---

## 11. Symbol

`symbol` must already be canonical:

```text
non-empty
trimmed
uppercase
```

Examples:

```text
AAPL   valid
MSFT   valid

aapl    invalid
 AAPL   invalid
""      invalid
```

Do not silently normalize malformed order symbols.

---

## 12. Quantity

`quantity` represents requested shares.

It must be:

- Python `int`;
- strictly greater than zero.

Reject:

```text
0
negative integers
bool
float
string
```

Examples:

```text
100   valid
1     valid

0     invalid
-100  invalid
True  invalid
100.0 invalid
```

Fractional shares remain outside current QuantForge scope.

---

## 13. Timestamp

`timestamp` means:

> the time at which the order was submitted into the trading/execution system.

It does NOT mean:

- fill time;
- exchange acknowledgement time;
- settlement time.

The timestamp must:

- be a `datetime`;
- be timezone-aware;
- have non-None `utcoffset()`.

Naive timestamps are rejected.

---

## 14. Market Order

A market order is represented as:

```python
Order(
    ...,
    order_type=OrderType.MARKET,
    limit_price=None,
)
```

For market orders:

```text
limit_price MUST be None
```

Providing a limit price with a market order is invalid.

SPEC-011 does not determine the market order's eventual fill price.

---

## 15. Limit Order

A limit order requires:

```text
limit_price
```

The limit price must be:

- Python `float`;
- finite;
- strictly greater than zero.

Reject:

```text
int
bool
NaN
+Inf
-Inf
0.0
negative values
```

---

## 16. Conventional Limit Semantics

Future execution logic will interpret:

```text
BUY LIMIT P
```

as unwilling to execute above `P`.

And:

```text
SELL LIMIT P
```

as unwilling to execute below `P`.

SPEC-011 documents this convention but does not implement matching or fill eligibility.

---

## 17. Market / Limit Invariant

The following must hold:

```text
MARKET → limit_price is None
LIMIT  → valid finite positive float limit_price
```

No ambiguous order representation is allowed.

---

## 18. Signed Quantity Bridge

Provide a derived property:

```python
order.signed_quantity
```

with:

```text
BUY  quantity Q → +Q
SELL quantity Q → -Q
```

Example:

```python
Order(side=OrderSide.BUY, quantity=100).signed_quantity
# 100
```

```python
Order(side=OrderSide.SELL, quantity=100).signed_quantity
# -100
```

This property exists solely as a bridge to future execution/accounting integration.

The stored quantity itself remains positive.

---

## 19. Optional Convenience Properties

Minimal convenience properties may include:

```python
order.is_buy
order.is_sell
```

if useful.

Do not add unnecessary order abstractions.

---

## 20. Order Is Intent, Not Outcome

An Order must not contain:

```text
filled_quantity
remaining_quantity
average_fill_price
fill_price
commission
slippage
market_impact
realized_pnl
portfolio_cash
position
```

Those represent downstream state/outcomes.

---

## 21. Order Is Not a Signal

An Order must not contain:

```text
score
alpha
feature values
strategy context
```

A future portfolio-construction/orchestration layer determines how signals become orders.

This separation allows:

```text
same strategy
+
different sizing policy
→
different orders
```

without modifying strategy code.

---

## 22. No Portfolio State

Order must not contain:

```text
cash
equity
current_position
target_weight
buying_power
leverage
```

Those belong to portfolio/risk layers.

---

## 23. No Execution State

Order must not contain:

```text
status
exchange status
filled quantity
remaining quantity
execution timestamp
fill records
```

Order lifecycle state will be introduced only when execution requirements are understood.

---

## 24. Immutability

`Order` must be:

```python
@dataclass(frozen=True, slots=True)
```

or equivalent.

After construction:

```python
order.quantity = 200
```

must fail.

If an order is later amended, that should be modeled explicitly rather than mutating an existing historical order object.

---

## 25. Determinism

Given identical constructor values:

```text
same inputs
→
equal Order values
```

No field may depend on:

```text
wall-clock time
random UUID generation
network state
global mutable counters
filesystem
```

This is why `order_id` is caller supplied.

---

## 26. Equality and Hashing

Value-equal Orders should compare equal.

Order must be hashable if naturally supported by the immutable representation.

This will allow future event/replay tests to use Orders deterministically.

---

## 27. Error Handling

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
order_id=123              → TypeError
order_id=""               → ValueError

symbol="aapl"             → ValueError

side="buy"                → TypeError
quantity=True             → TypeError
quantity=-100             → ValueError

timestamp naive           → ValueError

MARKET + limit_price=50.0 → ValueError

LIMIT + limit_price=None  → ValueError
LIMIT + limit_price=50    → TypeError
LIMIT + limit_price=NaN   → ValueError
```

Do not silently repair malformed Orders.

---

## 28. Module Structure

Preferred:

```text
src/quantforge/orders/
    __init__.py
    base.py
```

Preferred imports:

```python
from quantforge.orders import (
    Order,
    OrderSide,
    OrderType,
)
```

A similarly clean equivalent package structure is acceptable.

---

## 29. Dependency Policy

SPEC-011 introduces no runtime dependency.

Use only Python standard-library functionality.

Do not depend on:

```text
portfolio accounting
strategies
features
Parquet
PyArrow
execution packages
```

The Order domain should remain independently testable.

---

## 30. Tests — Enums

Test:

```text
OrderSide.BUY
OrderSide.SELL
OrderType.MARKET
OrderType.LIMIT
stable enum values
```

---

## 31. Tests — Market Orders

Test:

```text
market buy
market sell
positive quantity
canonical symbol
aware timestamp
limit_price=None
signed_quantity buy
signed_quantity sell
```

---

## 32. Tests — Limit Orders

Test:

```text
limit buy
limit sell
valid positive float limit price
signed quantity
```

---

## 33. Tests — Invalid Quantity

Test:

```text
0
negative
True
False
float
string
```

---

## 34. Tests — Limit-Price Invariants

Test:

```text
MARKET + None            valid
MARKET + price           invalid

LIMIT + positive float   valid
LIMIT + None             invalid
LIMIT + integer          invalid
LIMIT + bool             invalid
LIMIT + 0                invalid
LIMIT + negative         invalid
LIMIT + NaN              invalid
LIMIT + +Inf             invalid
LIMIT + -Inf             invalid
```

---

## 35. Tests — Timestamp

Test:

```text
UTC timestamp
non-UTC aware timestamp
naive datetime rejected
tzinfo with utcoffset=None rejected
non-datetime rejected
```

---

## 36. Tests — Identity

Test:

```text
valid opaque order ID
empty ID rejected
whitespace-only ID rejected
surrounding whitespace rejected
non-string rejected
same values compare equal
different ID makes orders unequal
hashability
```

---

## 37. Tests — Immutability

Attempt mutation of every Order field.

All mutation attempts must fail.

---

## 38. Architecture Boundary Tests

Structurally verify Order contains exactly:

```text
order_id
symbol
side
quantity
order_type
timestamp
limit_price
```

and does NOT contain:

```text
score
alpha
strategy_name
target_weight
cash
equity
position
filled_quantity
remaining_quantity
fill_price
average_fill_price
commission
slippage
market_impact
realized_pnl
status
```

---

## 39. Accounting Bridge Test

Create:

```text
BUY 100
```

and verify:

```text
signed_quantity == +100
```

Create:

```text
SELL 100
```

and verify:

```text
signed_quantity == -100
```

Do NOT call `PortfolioState.apply_fill()` in SPEC-011.

The bridge is semantic only.

Actual Order → Fill → Accounting integration belongs later.

---

## 40. No Lifecycle Semantics

SPEC-011 intentionally has no:

```text
NEW
OPEN
PARTIALLY_FILLED
FILLED
CANCELLED
REJECTED
```

state machine.

Those concepts should be designed together with execution behavior rather than guessed prematurely.

---

## 41. No Time-in-Force

SPEC-011 intentionally omits:

```text
DAY
GTC
IOC
FOK
```

because the current backtesting execution model has not yet defined order persistence across events/sessions.

Add those only when actual simulator requirements justify them.

---

## 42. Performance

Order-domain construction and validation are expected to be constant-time.

No special optimization is required.

Correctness, explicit semantics, and immutability are higher priorities.

---

## 43. Engineering Decision Expected

Record the next engineering decision describing why QuantForge uses:

```text
explicit BUY/SELL side
+
positive integer requested quantity
+
caller-supplied deterministic order IDs
+
separate MARKET/LIMIT semantics
```

and why lifecycle/fill state is excluded from immutable Order intent.

---

## 44. Acceptance Criteria

- [x] orders package exists.
- [x] `OrderSide` exists.
- [x] BUY exists.
- [x] SELL exists.
- [x] `OrderType` exists.
- [x] MARKET exists.
- [x] LIMIT exists.
- [x] `Order` exists.
- [x] Order is immutable.
- [x] Order is hashable.
- [x] caller supplies order ID.
- [x] Order does not generate random IDs.
- [x] order ID must be non-empty string.
- [x] surrounding order-ID whitespace is rejected.
- [x] canonical symbol is enforced.
- [x] side must be `OrderSide`.
- [x] order type must be `OrderType`.
- [x] quantity must be positive integer.
- [x] boolean quantity is rejected.
- [x] timestamp must be rigorously timezone-aware.
- [x] MARKET requires `limit_price=None`.
- [x] LIMIT requires limit price.
- [x] limit price must be Python float.
- [x] limit price must be finite.
- [x] limit price must be positive.
- [x] BUY signed quantity is positive.
- [x] SELL signed quantity is negative.
- [x] Order has no Signal score.
- [x] Order has no target portfolio weight.
- [x] Order has no portfolio cash/equity.
- [x] Order has no fill quantity.
- [x] Order has no fill price.
- [x] Order has no commission/slippage.
- [x] Order has no execution status.
- [x] no order lifecycle state machine is introduced.
- [x] no TIF semantics are introduced.
- [x] no execution simulator is introduced.
- [x] no Fill model is introduced.
- [x] no portfolio integration is performed.
- [x] deterministic equality is tested.
- [x] immutability is tested.
- [x] market-buy behavior is tested.
- [x] market-sell behavior is tested.
- [x] limit-buy validation is tested.
- [x] limit-sell validation is tested.
- [x] rigorous timezone validation is tested.
- [x] architecture exclusions are tested.
- [x] no new runtime dependency is introduced.
- [x] pytest passes.
- [x] Ruff lint passes.
- [x] Ruff formatting passes.
- [x] strict mypy passes.
- [x] `git diff --check` passes.
- [x] specification index is updated.
- [x] architecture documentation reflects only implemented behavior.
- [x] meaningful design decisions or bugs are recorded.

---

## 45. Dependencies

No direct dependency on Strategy or Portfolio Accounting.

Conceptually connects future:

```text
Portfolio Construction
→ Order
→ Execution
```

New runtime dependencies:

```text
none
```

Expected next specification:

```text
SPEC-012 — Event System
```

Do not begin SPEC-012 during implementation.

---

## 46. Completion Summary

Status: Completed

Files created: `src/quantforge/orders/__init__.py`, `src/quantforge/orders/base.py`, and
`tests/test_order_domain.py`.

Files modified: `ARCHITECTURE.md`, `docs/ENGINEERING_LOG.md`, `docs/specs/INDEX.md`, and this
specification.

Public API: `OrderSide`, `OrderType`, and immutable `Order`, exported from
`quantforge.orders`.

Order-side convention: requested quantity is always a strictly positive integer. `OrderSide.BUY`
maps to positive `signed_quantity`; `OrderSide.SELL` maps to negative `signed_quantity`.

Order-type semantics: MARKET orders prohibit a limit price. LIMIT orders require a finite,
strictly positive Python `float` limit price.

Validation: caller-supplied IDs must be non-empty strings without surrounding whitespace, symbols
must already be canonical, side and type must be their exact enums, quantity must be a non-boolean
positive integer, and timestamps must be rigorously timezone-aware.

Tests added: 65 deterministic cases cover enums, exact fields, caller IDs, validation boundaries,
BUY/SELL signed quantities, MARKET/LIMIT rules, timestamps, equality, hashing, immutability, and
architecture exclusions.

Commands run: pytest, Ruff lint, Ruff format check, strict mypy, and `git diff --check` all pass.
No Markdown validator is configured.

Known limitations: Order is execution intent only. Global ID uniqueness, lifecycle, TIF, fills,
partial fills, cancellation, amendment, execution costs, and portfolio integration remain outside
this specification.

Engineering log entries: `DECISION-013` records explicit side/positive-quantity semantics,
caller-owned identity, type-specific price rules, and separation from lifecycle and fills.

Expected next specification:

`SPEC-012 — Event System`
