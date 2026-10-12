"""Deterministic tests for immutable order execution intent."""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from math import inf, nan

import pytest

import quantforge.orders as orders_module
from quantforge.orders import Order, OrderSide, OrderType

SUBMITTED_AT = datetime(2026, 10, 12, 14, 30, tzinfo=UTC)


class _NoOffsetTimezone(tzinfo):
    def utcoffset(self, dt: datetime | None) -> None:
        return None

    def dst(self, dt: datetime | None) -> None:
        return None

    def tzname(self, dt: datetime | None) -> str:
        return "NO_OFFSET"


def make_order(**overrides: object) -> Order:
    values: dict[str, object] = {
        "order_id": "order_001",
        "symbol": "AAPL",
        "side": OrderSide.BUY,
        "quantity": 100,
        "order_type": OrderType.MARKET,
        "timestamp": SUBMITTED_AT,
        "limit_price": None,
    }
    values.update(overrides)
    return Order(**values)  # type: ignore[arg-type]


def test_order_side_has_only_stable_buy_and_sell_values() -> None:
    assert tuple(OrderSide) == (OrderSide.BUY, OrderSide.SELL)
    assert OrderSide.BUY.value == "buy"
    assert OrderSide.SELL.value == "sell"


def test_order_type_has_only_stable_market_and_limit_values() -> None:
    assert tuple(OrderType) == (OrderType.MARKET, OrderType.LIMIT)
    assert OrderType.MARKET.value == "market"
    assert OrderType.LIMIT.value == "limit"


@pytest.mark.parametrize(
    ("side", "expected_signed_quantity"),
    [(OrderSide.BUY, 100), (OrderSide.SELL, -100)],
)
def test_market_order_uses_positive_stored_quantity_and_signed_bridge(
    side: OrderSide,
    expected_signed_quantity: int,
) -> None:
    order = make_order(side=side)

    assert tuple(field.name for field in fields(Order)) == (
        "order_id",
        "symbol",
        "side",
        "quantity",
        "order_type",
        "timestamp",
        "limit_price",
    )
    assert order.quantity == 100
    assert order.signed_quantity == expected_signed_quantity
    assert order.order_type is OrderType.MARKET
    assert order.limit_price is None
    assert not hasattr(order, "__dict__")


@pytest.mark.parametrize(
    ("side", "expected_signed_quantity"),
    [(OrderSide.BUY, 25), (OrderSide.SELL, -25)],
)
def test_limit_order_requires_price_and_preserves_side_semantics(
    side: OrderSide,
    expected_signed_quantity: int,
) -> None:
    order = make_order(
        side=side,
        quantity=25,
        order_type=OrderType.LIMIT,
        limit_price=123.45,
    )

    assert order.quantity == 25
    assert order.signed_quantity == expected_signed_quantity
    assert order.limit_price == 123.45


@pytest.mark.parametrize("order_id", ["order_001", "run42_order_17", "abc123", "opaque-id"])
def test_order_accepts_caller_supplied_opaque_id(order_id: str) -> None:
    order = make_order(order_id=order_id)

    assert order.order_id == order_id


@pytest.mark.parametrize("order_id", ["", " ", "\t\n"])
def test_order_rejects_empty_or_whitespace_only_id(order_id: str) -> None:
    with pytest.raises(ValueError, match="order_id must not be empty"):
        make_order(order_id=order_id)


@pytest.mark.parametrize("order_id", [" order_001", "order_001 ", "\torder_001\n"])
def test_order_rejects_surrounding_id_whitespace(order_id: str) -> None:
    with pytest.raises(ValueError, match="surrounding whitespace"):
        make_order(order_id=order_id)


def test_order_rejects_non_string_id() -> None:
    with pytest.raises(TypeError, match="order_id must be a string"):
        make_order(order_id=1)


def test_domain_does_not_enforce_global_order_id_uniqueness() -> None:
    buy = make_order(order_id="shared_id", side=OrderSide.BUY)
    sell = make_order(order_id="shared_id", side=OrderSide.SELL)

    assert buy.order_id == sell.order_id == "shared_id"
    assert buy != sell


@pytest.mark.parametrize("symbol", ["", " ", "aapl", " AAPL "])
def test_order_rejects_noncanonical_symbol(symbol: str) -> None:
    with pytest.raises(ValueError, match="symbol"):
        make_order(symbol=symbol)


def test_order_rejects_non_string_symbol() -> None:
    with pytest.raises(TypeError, match="symbol must be a string"):
        make_order(symbol=1)


@pytest.mark.parametrize("side", ["buy", "sell", 1])
def test_order_requires_order_side_enum(side: object) -> None:
    with pytest.raises(TypeError, match="side must be an OrderSide"):
        make_order(side=side)


@pytest.mark.parametrize("order_type", ["market", "limit", 1])
def test_order_requires_order_type_enum(order_type: object) -> None:
    with pytest.raises(TypeError, match="order_type must be an OrderType"):
        make_order(order_type=order_type)


@pytest.mark.parametrize("quantity", [0, -1, -100])
def test_order_rejects_nonpositive_quantity(quantity: int) -> None:
    with pytest.raises(ValueError, match="quantity must be greater than zero"):
        make_order(quantity=quantity)


@pytest.mark.parametrize("quantity", [True, False, 100.0, "100"])
def test_order_rejects_boolean_or_noninteger_quantity(quantity: object) -> None:
    with pytest.raises(TypeError, match="quantity must be an integer and must not be boolean"):
        make_order(quantity=quantity)


def test_order_preserves_aware_non_utc_submission_timestamp() -> None:
    eastern = timezone(timedelta(hours=-4))
    timestamp = datetime(2026, 10, 12, 10, 30, tzinfo=eastern)
    order = make_order(timestamp=timestamp)

    assert order.timestamp is timestamp


def test_order_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        make_order(timestamp=datetime(2026, 10, 12, 14, 30))


def test_order_rejects_timestamp_whose_timezone_has_no_utc_offset() -> None:
    timestamp = datetime(2026, 10, 12, tzinfo=_NoOffsetTimezone())
    assert timestamp.tzinfo is not None
    assert timestamp.utcoffset() is None

    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        make_order(timestamp=timestamp)


def test_order_rejects_non_datetime_timestamp() -> None:
    with pytest.raises(TypeError, match="timestamp must be a datetime"):
        make_order(timestamp="2026-10-12T14:30:00Z")


@pytest.mark.parametrize("limit_price", [1.0, 100.0, 0.01])
def test_limit_order_accepts_positive_finite_float_price(limit_price: float) -> None:
    order = make_order(order_type=OrderType.LIMIT, limit_price=limit_price)

    assert order.limit_price == limit_price


@pytest.mark.parametrize("limit_price", [1.0, 50, True])
def test_market_order_rejects_any_limit_price(limit_price: object) -> None:
    with pytest.raises(ValueError, match="market orders must have limit_price=None"):
        make_order(limit_price=limit_price)


def test_limit_order_rejects_missing_limit_price() -> None:
    with pytest.raises(ValueError, match="limit orders require a limit_price"):
        make_order(order_type=OrderType.LIMIT, limit_price=None)


@pytest.mark.parametrize("limit_price", [50, True])
def test_limit_order_rejects_nonfloat_limit_price(limit_price: object) -> None:
    with pytest.raises(TypeError, match="limit_price must be a float"):
        make_order(order_type=OrderType.LIMIT, limit_price=limit_price)


@pytest.mark.parametrize("limit_price", [0.0, -1.0, nan, inf, -inf])
def test_limit_order_rejects_nonpositive_or_nonfinite_limit_price(limit_price: float) -> None:
    with pytest.raises(ValueError, match="limit_price must be finite and greater than zero"):
        make_order(order_type=OrderType.LIMIT, limit_price=limit_price)


def test_value_equal_orders_compare_equal_and_hash_identically() -> None:
    first = make_order()
    second = make_order()

    assert first is not second
    assert first == second
    assert hash(first) == hash(second)
    assert {first, second} == {first}
    assert {first: "found"}[second] == "found"


def test_different_caller_supplied_id_makes_orders_unequal() -> None:
    assert make_order(order_id="order_001") != make_order(order_id="order_002")


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("order_id", "order_002"),
        ("symbol", "MSFT"),
        ("side", OrderSide.SELL),
        ("quantity", 200),
        ("order_type", OrderType.LIMIT),
        ("timestamp", datetime(2026, 10, 12, 14, 31, tzinfo=UTC)),
        ("limit_price", 100.0),
    ],
)
def test_order_rejects_mutation_of_every_field(field_name: str, replacement: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(make_order(), field_name, replacement)


def test_order_contains_only_execution_intent_fields() -> None:
    order = make_order()

    assert tuple(field.name for field in fields(Order)) == (
        "order_id",
        "symbol",
        "side",
        "quantity",
        "order_type",
        "timestamp",
        "limit_price",
    )
    for excluded in (
        "score",
        "alpha",
        "strategy_name",
        "target_weight",
        "cash",
        "equity",
        "position",
        "filled_quantity",
        "remaining_quantity",
        "fill_price",
        "average_fill_price",
        "commission",
        "slippage",
        "market_impact",
        "realized_pnl",
        "status",
        "time_in_force",
    ):
        assert not hasattr(order, excluded)


def test_orders_module_introduces_no_fill_execution_or_lifecycle_types() -> None:
    for excluded in (
        "Fill",
        "ExecutionSimulator",
        "OrderStatus",
        "TimeInForce",
        "CommissionModel",
        "SlippageModel",
        "Event",
    ):
        assert not hasattr(orders_module, excluded)
