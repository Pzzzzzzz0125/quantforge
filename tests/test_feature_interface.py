"""Tests for the immutable causal feature-domain contracts."""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, tzinfo
from math import inf, nan

import pytest

from quantforge.domain import Bar
from quantforge.features import Feature, FeatureSpec, FeatureValue, FeatureWindow

START = datetime(2026, 9, 3, 9, 30, tzinfo=UTC)


class _NoOffsetTimezone(tzinfo):
    def utcoffset(self, dt: datetime | None) -> None:
        return None

    def dst(self, dt: datetime | None) -> None:
        return None

    def tzname(self, dt: datetime | None) -> str:
        return "NO_OFFSET"


class _CurrentCloseFeature:
    def __init__(self, lookback_bars: int = 1) -> None:
        self._spec = FeatureSpec(name="current_close", lookback_bars=lookback_bars)

    @property
    def spec(self) -> FeatureSpec:
        return self._spec

    def compute(self, window: FeatureWindow) -> float | None:
        if window.size < self.spec.lookback_bars:
            return None
        return window.current.close


def make_bar(
    minute: int = 0,
    *,
    symbol: str = "AAPL",
    close: float = 101.0,
) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=START + timedelta(minutes=minute),
        open=100.0,
        high=max(102.0, close),
        low=min(99.0, close),
        close=close,
        volume=1_000,
    )


def make_value(**overrides: object) -> FeatureValue:
    values: dict[str, object] = {
        "feature_name": "current_close",
        "symbol": "AAPL",
        "timestamp": START,
        "value": 101.0,
    }
    values.update(overrides)
    return FeatureValue(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("lookback_bars", [1, 2, 20])
def test_feature_spec_accepts_valid_metadata(lookback_bars: int) -> None:
    spec = FeatureSpec(name="return_1", lookback_bars=lookback_bars)

    assert spec.name == "return_1"
    assert spec.lookback_bars == lookback_bars
    assert not hasattr(spec, "__dict__")


@pytest.mark.parametrize("name", ["", " ", " return_1", "return_1 "])
def test_feature_spec_rejects_empty_or_whitespace_name(name: str) -> None:
    with pytest.raises(ValueError, match="feature name"):
        FeatureSpec(name=name, lookback_bars=1)


@pytest.mark.parametrize("name", ["Return_1", "1_return", "return-1", "return.value"])
def test_feature_spec_rejects_invalid_identifier(name: str) -> None:
    with pytest.raises(ValueError, match=r"\[a-z\]\[a-z0-9_\]\*"):
        FeatureSpec(name=name, lookback_bars=1)


def test_feature_spec_rejects_non_string_name() -> None:
    with pytest.raises(TypeError, match="feature name must be a string"):
        FeatureSpec(name=1, lookback_bars=1)  # type: ignore[arg-type]


@pytest.mark.parametrize("lookback_bars", [0, -1])
def test_feature_spec_rejects_non_positive_lookback(lookback_bars: int) -> None:
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        FeatureSpec(name="current_close", lookback_bars=lookback_bars)


@pytest.mark.parametrize("lookback_bars", [True, 1.0, "1"])
def test_feature_spec_rejects_invalid_lookback_type(lookback_bars: object) -> None:
    with pytest.raises(TypeError, match="must be an integer and must not be boolean"):
        FeatureSpec(name="current_close", lookback_bars=lookback_bars)  # type: ignore[arg-type]


def test_feature_spec_is_immutable_and_hashable() -> None:
    spec = FeatureSpec(name="current_close", lookback_bars=1)

    with pytest.raises(FrozenInstanceError):
        spec.name = "other"  # type: ignore[misc]
    assert {spec: "registered"}[spec] == "registered"


def test_one_bar_window_exposes_derived_properties() -> None:
    current = make_bar()
    window = FeatureWindow(bars=(current,))

    assert tuple(field.name for field in fields(FeatureWindow)) == ("bars",)
    assert window.bars == (current,)
    assert isinstance(window.bars, tuple)
    assert window.symbol == "AAPL"
    assert window.as_of == current.timestamp
    assert window.current is current
    assert window.size == 1
    assert not hasattr(window, "__dict__")


def test_multiple_bar_window_preserves_strictly_increasing_bars() -> None:
    bars = (make_bar(0), make_bar(1), make_bar(2))

    window = FeatureWindow(bars=bars)

    assert window.bars is bars
    assert window.current is bars[-1]
    assert window.as_of == bars[-1].timestamp
    assert window.size == 3


def test_feature_window_rejects_non_tuple_storage() -> None:
    with pytest.raises(TypeError, match="bars must be a tuple"):
        FeatureWindow(bars=[make_bar()])  # type: ignore[arg-type]


def test_feature_window_rejects_empty_tuple() -> None:
    with pytest.raises(ValueError, match="at least one Bar"):
        FeatureWindow(bars=())


@pytest.mark.parametrize("position", [0, 1])
def test_feature_window_rejects_non_bar_element(position: int) -> None:
    bars: tuple[object, ...] = (make_bar(), make_bar(1))
    invalid = bars[:position] + ("not-a-bar",) + bars[position + 1 :]

    with pytest.raises(TypeError, match="only Bar instances"):
        FeatureWindow(bars=invalid)  # type: ignore[arg-type]


def test_feature_window_rejects_mixed_symbols() -> None:
    with pytest.raises(ValueError, match="exactly one symbol"):
        FeatureWindow(bars=(make_bar(), make_bar(1, symbol="MSFT")))


def test_feature_window_rejects_duplicate_timestamps() -> None:
    with pytest.raises(ValueError, match="duplicates the previous timestamp"):
        FeatureWindow(bars=(make_bar(), make_bar()))


def test_feature_window_rejects_decreasing_timestamps() -> None:
    with pytest.raises(ValueError, match="earlier than the previous timestamp"):
        FeatureWindow(bars=(make_bar(2), make_bar(1)))


def test_feature_window_is_immutable_and_hashable() -> None:
    window = FeatureWindow(bars=(make_bar(),))

    with pytest.raises(FrozenInstanceError):
        window.bars = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        window.current.close = 1.0  # type: ignore[misc]
    assert {window: "cached"}[window] == "cached"


def test_feature_value_exposes_exact_fields_and_valid_value() -> None:
    value = make_value()

    assert tuple(field.name for field in fields(FeatureValue)) == (
        "feature_name",
        "symbol",
        "timestamp",
        "value",
    )
    assert value == FeatureValue("current_close", "AAPL", START, 101.0)
    assert not hasattr(value, "__dict__")


@pytest.mark.parametrize("feature_name", ["", " Close", "Close", "close-price"])
def test_feature_value_rejects_invalid_feature_name(feature_name: str) -> None:
    with pytest.raises(ValueError, match="feature name"):
        make_value(feature_name=feature_name)


@pytest.mark.parametrize("symbol", ["", " ", "aapl", " AAPL "])
def test_feature_value_rejects_noncanonical_symbol(symbol: str) -> None:
    with pytest.raises(ValueError, match="symbol"):
        make_value(symbol=symbol)


def test_feature_value_rejects_incorrect_metadata_types() -> None:
    with pytest.raises(TypeError, match="feature name must be a string"):
        make_value(feature_name=1)
    with pytest.raises(TypeError, match="symbol must be a string"):
        make_value(symbol=1)
    with pytest.raises(TypeError, match="timestamp must be a datetime"):
        make_value(timestamp="2026-09-03T09:30:00Z")


def test_feature_value_accepts_timezone_aware_timestamp() -> None:
    timestamp = datetime(2026, 9, 3, 9, 30, tzinfo=UTC)

    assert make_value(timestamp=timestamp).timestamp is timestamp


@pytest.mark.parametrize(
    "timestamp",
    [datetime(2026, 9, 3, 9, 30), datetime(2026, 9, 3, tzinfo=_NoOffsetTimezone())],
)
def test_feature_value_rejects_timestamp_without_utc_offset(timestamp: datetime) -> None:
    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        make_value(timestamp=timestamp)


@pytest.mark.parametrize("value", [0, True])
def test_feature_value_rejects_non_float_value(value: object) -> None:
    with pytest.raises(TypeError, match="value must be a float"):
        make_value(value=value)


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_feature_value_rejects_non_finite_value(value: float) -> None:
    with pytest.raises(ValueError, match="value must be finite"):
        make_value(value=value)


def test_feature_value_is_immutable_and_hashable() -> None:
    value = make_value()

    with pytest.raises(FrozenInstanceError):
        value.value = 102.0  # type: ignore[misc]
    assert {value: "stored"}[value] == "stored"


def compute_as_feature(feature: Feature, window: FeatureWindow) -> float | None:
    """Exercise static structural compatibility with the public protocol."""
    return feature.compute(window)


def test_test_only_implementation_conforms_to_feature_protocol() -> None:
    window = FeatureWindow(bars=(make_bar(close=103.0),))

    assert compute_as_feature(_CurrentCloseFeature(), window) == 103.0


def test_feature_returns_none_during_warm_up() -> None:
    feature = _CurrentCloseFeature(lookback_bars=3)

    assert feature.compute(FeatureWindow((make_bar(0),))) is None
    assert feature.compute(FeatureWindow((make_bar(0), make_bar(1)))) is None
    assert feature.compute(FeatureWindow((make_bar(0), make_bar(1), make_bar(2)))) == 101.0


def test_feature_receives_only_the_causal_window() -> None:
    bars = (make_bar(0, close=100.0), make_bar(1, close=101.0), make_bar(2, close=999.0))
    causal_window = FeatureWindow(bars=bars[:2])

    feature = _CurrentCloseFeature()

    assert causal_window.as_of == bars[1].timestamp
    assert bars[2] not in causal_window.bars
    assert feature.compute(causal_window) == 101.0
    assert feature.compute(causal_window) == feature.compute(causal_window)
