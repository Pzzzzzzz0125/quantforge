"""Tests for the canonical market bar domain object."""

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from math import inf, nan

import pytest

from quantforge.domain import Bar

BAR_TIMESTAMP = datetime(2026, 8, 31, tzinfo=UTC)
PRICE_FIELDS = ("open", "high", "low", "close")


def make_bar(
    *,
    symbol: str = "AAPL",
    timestamp: datetime = BAR_TIMESTAMP,
    open_price: float = 100.0,
    high: float = 105.0,
    low: float = 95.0,
    close: float = 102.0,
    volume: int = 1_000,
) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def test_bar_exposes_exactly_the_approved_fields() -> None:
    assert tuple(field.name for field in fields(Bar)) == (
        "symbol",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )


def test_bar_constructs_with_valid_ohlcv_values() -> None:
    bar = make_bar()

    assert bar == Bar("AAPL", BAR_TIMESTAMP, 100.0, 105.0, 95.0, 102.0, 1_000)
    assert not hasattr(bar, "__dict__")


@pytest.mark.parametrize(
    ("source_symbol", "normalized_symbol"),
    [
        ("aapl", "AAPL"),
        (" Aapl ", "AAPL"),
        ("\tspy\n", "SPY"),
    ],
)
def test_bar_normalizes_symbol_deterministically(
    source_symbol: str, normalized_symbol: str
) -> None:
    assert make_bar(symbol=source_symbol).symbol == normalized_symbol


@pytest.mark.parametrize("symbol", ["", " ", "\t\n"])
def test_bar_rejects_empty_symbol(symbol: str) -> None:
    with pytest.raises(ValueError, match="symbol must not be empty"):
        make_bar(symbol=symbol)


def test_bar_rejects_non_string_symbol() -> None:
    with pytest.raises(TypeError, match="symbol must be a string"):
        Bar(
            symbol=123,  # type: ignore[arg-type]
            timestamp=BAR_TIMESTAMP,
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1_000,
        )


def test_bar_preserves_timezone_aware_timestamp() -> None:
    eastern = timezone(timedelta(hours=-5))
    timestamp = datetime(2026, 8, 31, 9, 30, tzinfo=eastern)

    assert make_bar(timestamp=timestamp).timestamp is timestamp


def test_bar_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        make_bar(timestamp=datetime(2026, 8, 31))


def test_bar_rejects_non_datetime_timestamp() -> None:
    with pytest.raises(TypeError, match="timestamp must be a datetime"):
        Bar(
            symbol="AAPL",
            timestamp="2026-08-31T00:00:00Z",  # type: ignore[arg-type]
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1_000,
        )


@pytest.mark.parametrize("field_name", PRICE_FIELDS)
@pytest.mark.parametrize("invalid_price", [0.0, -1.0, nan, inf, -inf])
def test_bar_rejects_non_positive_or_non_finite_price(
    field_name: str, invalid_price: float
) -> None:
    with pytest.raises(ValueError, match=rf"{field_name} must be finite and greater than zero"):
        replace(make_bar(), **{field_name: invalid_price})  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", PRICE_FIELDS)
@pytest.mark.parametrize("invalid_price", [1, True])
def test_bar_rejects_non_float_price(field_name: str, invalid_price: object) -> None:
    with pytest.raises(TypeError, match=rf"{field_name} must be a float"):
        replace(make_bar(), **{field_name: invalid_price})  # type: ignore[arg-type]


def test_bar_allows_zero_volume() -> None:
    assert make_bar(volume=0).volume == 0


def test_bar_rejects_negative_volume() -> None:
    with pytest.raises(ValueError, match="volume must be a non-negative integer"):
        make_bar(volume=-1)


def test_bar_rejects_boolean_volume() -> None:
    with pytest.raises(TypeError, match="volume must be an integer and must not be boolean"):
        make_bar(volume=True)


def test_bar_rejects_non_integer_volume() -> None:
    with pytest.raises(TypeError, match="volume must be an integer and must not be boolean"):
        Bar(
            symbol="AAPL",
            timestamp=BAR_TIMESTAMP,
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1.0,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("open_price", "high", "low", "close", "invalid_field"),
    [
        (10.0, 9.0, 8.0, 8.5, "high"),
        (8.0, 9.0, 7.0, 10.0, "high"),
        (8.0, 9.0, 10.0, 8.5, "high"),
        (10.0, 12.0, 11.0, 12.0, "low"),
        (12.0, 12.0, 11.0, 10.0, "low"),
    ],
)
def test_bar_rejects_inconsistent_ohlc_values(
    open_price: float,
    high: float,
    low: float,
    close: float,
    invalid_field: str,
) -> None:
    with pytest.raises(ValueError, match=invalid_field):
        make_bar(open_price=open_price, high=high, low=low, close=close)


@pytest.mark.parametrize(
    ("open_price", "high", "low", "close"),
    [
        (10.0, 10.0, 10.0, 10.0),
        (10.0, 10.0, 9.0, 9.0),
    ],
)
def test_bar_allows_equal_ohlc_boundaries(
    open_price: float, high: float, low: float, close: float
) -> None:
    bar = make_bar(open_price=open_price, high=high, low=low, close=close)

    assert (bar.open, bar.high, bar.low, bar.close) == (open_price, high, low, close)


@pytest.mark.parametrize(
    ("field_name", "new_value"),
    [
        ("symbol", "MSFT"),
        ("timestamp", datetime(2026, 9, 1, tzinfo=UTC)),
        ("open", 101.0),
        ("high", 106.0),
        ("low", 94.0),
        ("close", 103.0),
        ("volume", 2_000),
    ],
)
def test_bar_rejects_mutation_of_every_field(field_name: str, new_value: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(make_bar(), field_name, new_value)


def test_equivalent_normalized_bars_compare_equal_and_hash_identically() -> None:
    lowercase_bar = make_bar(symbol=" aapl ")
    uppercase_bar = make_bar(symbol="AAPL")

    assert lowercase_bar == uppercase_bar
    assert hash(lowercase_bar) == hash(uppercase_bar)
    assert {lowercase_bar, uppercase_bar} == {uppercase_bar}
    assert {lowercase_bar: "found"}[uppercase_bar] == "found"
