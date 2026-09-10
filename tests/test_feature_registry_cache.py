"""Tests for in-memory feature registration and exact-input caching."""

from datetime import UTC, datetime, timedelta
from math import inf, nan

import pytest

from quantforge.domain import Bar
from quantforge.features import (
    FeatureCache,
    FeatureRegistry,
    FeatureSpec,
    FeatureWindow,
)

START = datetime(2026, 9, 9, 9, 30, tzinfo=UTC)


class _TestFeature:
    def __init__(self, name: str, lookback_bars: int = 1) -> None:
        self._spec = FeatureSpec(name=name, lookback_bars=lookback_bars)
        self.compute_calls = 0

    @property
    def spec(self) -> FeatureSpec:
        return self._spec

    def compute(self, window: FeatureWindow) -> float | None:
        self.compute_calls += 1
        return window.current.close


class _InvalidSpecFeature:
    @property
    def spec(self) -> FeatureSpec:
        return "not-a-feature-spec"  # type: ignore[return-value]

    def compute(self, window: FeatureWindow) -> float | None:
        return window.current.close


def make_bar(
    minute: int,
    *,
    symbol: str = "AAPL",
    close: float = 101.0,
    volume: int = 1_000,
) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=START + timedelta(minutes=minute),
        open=100.0,
        high=max(102.0, close),
        low=min(99.0, close),
        close=close,
        volume=volume,
    )


def make_window(
    *,
    symbol: str = "AAPL",
    historical_minute: int = 0,
    historical_close: float = 101.0,
    historical_volume: int = 1_000,
    as_of_minute: int = 1,
) -> FeatureWindow:
    return FeatureWindow(
        bars=(
            make_bar(
                historical_minute,
                symbol=symbol,
                close=historical_close,
                volume=historical_volume,
            ),
            make_bar(as_of_minute, symbol=symbol, close=102.0, volume=2_000),
        )
    )


def test_empty_registry_has_immutable_empty_listing() -> None:
    registry = FeatureRegistry()

    assert len(registry) == 0
    assert registry.list_specs() == ()
    assert isinstance(registry.list_specs(), tuple)


def test_registry_registers_and_returns_the_same_feature_without_computing() -> None:
    registry = FeatureRegistry()
    feature = _TestFeature("current_close")

    registry.register(feature)

    assert registry.get("current_close") is feature
    assert registry.list_specs() == (feature.spec,)
    assert len(registry) == 1
    assert feature.compute_calls == 0


def test_registry_lists_specs_in_registration_order() -> None:
    registry = FeatureRegistry()
    first = _TestFeature("first_feature")
    second = _TestFeature("second_feature", lookback_bars=2)

    registry.register(first)
    registry.register(second)

    specs = registry.list_specs()
    assert specs == (first.spec, second.spec)
    assert isinstance(specs, tuple)


def test_registry_rejects_duplicate_name_without_replacement() -> None:
    registry = FeatureRegistry()
    original = _TestFeature("current_close", lookback_bars=1)
    collision = _TestFeature("current_close", lookback_bars=2)
    registry.register(original)

    with pytest.raises(ValueError, match="feature name 'current_close' is already registered"):
        registry.register(collision)

    assert registry.get("current_close") is original
    assert registry.list_specs() == (original.spec,)
    assert len(registry) == 1
    assert collision.compute_calls == 0


def test_registry_rejects_same_object_twice() -> None:
    registry = FeatureRegistry()
    feature = _TestFeature("current_close")
    registry.register(feature)

    with pytest.raises(ValueError, match="same feature object"):
        registry.register(feature)

    assert len(registry) == 1


def test_registry_rejects_invalid_exposed_spec() -> None:
    registry = FeatureRegistry()

    with pytest.raises(TypeError, match=r"feature\.spec must be a FeatureSpec"):
        registry.register(_InvalidSpecFeature())

    assert len(registry) == 0


@pytest.mark.parametrize("name", ["unknown_feature", " current_close ", "CURRENT_CLOSE"])
def test_registry_unknown_or_noncanonical_lookup_raises_key_error(name: str) -> None:
    registry = FeatureRegistry()
    feature = _TestFeature("current_close")
    registry.register(feature)

    with pytest.raises(KeyError):
        registry.get(name)

    assert registry.get("current_close") is feature


def test_empty_cache_misses_and_has_zero_length() -> None:
    cache = FeatureCache()

    assert len(cache) == 0
    with pytest.raises(KeyError):
        cache.get(FeatureSpec("current_close", 1), make_window())


def test_cache_round_trips_finite_float() -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    window = make_window()

    cache.put(spec, window, 102.0)

    assert cache.get(spec, window) == 102.0
    assert len(cache) == 1


def test_cached_none_is_distinct_from_cache_miss() -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 3)
    cached_window = make_window()
    uncached_window = make_window(as_of_minute=2)

    cache.put(spec, cached_window, None)

    assert cache.get(spec, cached_window) is None
    assert len(cache) == 1
    with pytest.raises(KeyError):
        cache.get(spec, uncached_window)


@pytest.mark.parametrize("value", [1, 0, True])
def test_cache_rejects_integer_and_boolean_values(value: object) -> None:
    cache = FeatureCache()

    with pytest.raises(TypeError, match="value must be a float or None"):
        cache.put(FeatureSpec("current_close", 1), make_window(), value)  # type: ignore[arg-type]

    assert len(cache) == 0


@pytest.mark.parametrize("value", [nan, inf, -inf])
def test_cache_rejects_non_finite_values(value: float) -> None:
    cache = FeatureCache()

    with pytest.raises(ValueError, match="value must be finite"):
        cache.put(FeatureSpec("current_close", 1), make_window(), value)

    assert len(cache) == 0


@pytest.mark.parametrize("method_name", ["put", "get"])
def test_cache_rejects_invalid_spec_type(method_name: str) -> None:
    cache = FeatureCache()

    with pytest.raises(TypeError, match="spec must be a FeatureSpec"):
        if method_name == "put":
            cache.put("current_close", make_window(), 1.0)  # type: ignore[arg-type]
        else:
            cache.get("current_close", make_window())  # type: ignore[arg-type]


@pytest.mark.parametrize("method_name", ["put", "get"])
def test_cache_rejects_invalid_window_type(method_name: str) -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)

    with pytest.raises(TypeError, match="window must be a FeatureWindow"):
        if method_name == "put":
            cache.put(spec, (), 1.0)  # type: ignore[arg-type]
        else:
            cache.get(spec, ())  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [1.25, None])
def test_reinserting_same_exact_result_is_idempotent(value: float | None) -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    window = make_window()

    cache.put(spec, window, value)
    cache.put(spec, window, value)

    assert cache.get(spec, window) == value
    assert len(cache) == 1


@pytest.mark.parametrize(
    ("original", "replacement"),
    [(1.25, 1.30), (None, 1.25), (1.25, None)],
)
def test_cache_rejects_conflicting_result(
    original: float | None,
    replacement: float | None,
) -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    window = make_window()
    cache.put(spec, window, original)

    with pytest.raises(ValueError, match="different result is already cached"):
        cache.put(spec, window, replacement)

    assert cache.get(spec, window) == original
    assert len(cache) == 1


def test_cache_clear_removes_float_and_none_entries() -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    first_window = make_window()
    second_window = make_window(as_of_minute=2)
    cache.put(spec, first_window, 1.0)
    cache.put(spec, second_window, None)

    cache.clear()

    assert len(cache) == 0
    with pytest.raises(KeyError):
        cache.get(spec, first_window)
    with pytest.raises(KeyError):
        cache.get(spec, second_window)


@pytest.mark.parametrize(
    "different_spec",
    [FeatureSpec("other_feature", 1), FeatureSpec("current_close", 2)],
)
def test_different_feature_specs_do_not_share_cache_entries(
    different_spec: FeatureSpec,
) -> None:
    cache = FeatureCache()
    window = make_window()
    cache.put(FeatureSpec("current_close", 1), window, 1.0)

    with pytest.raises(KeyError):
        cache.get(different_spec, window)


def test_different_symbol_does_not_share_cache_entry() -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    cache.put(spec, make_window(symbol="AAPL"), 1.0)

    with pytest.raises(KeyError):
        cache.get(spec, make_window(symbol="MSFT"))


def test_different_as_of_timestamp_does_not_share_cache_entry() -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    cache.put(spec, make_window(as_of_minute=1), 1.0)

    with pytest.raises(KeyError):
        cache.get(spec, make_window(as_of_minute=2))


def test_different_bar_count_does_not_share_cache_entry() -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    complete_window = make_window()
    cache.put(spec, complete_window, 1.0)

    with pytest.raises(KeyError):
        cache.get(spec, FeatureWindow((complete_window.current,)))


def test_different_historical_timestamp_does_not_share_cache_entry() -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    cache.put(spec, make_window(historical_minute=0, as_of_minute=2), 1.0)

    with pytest.raises(KeyError):
        cache.get(spec, make_window(historical_minute=1, as_of_minute=2))


def test_same_feature_symbol_and_as_of_with_different_historical_price_misses() -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    original = make_window(historical_close=101.0)
    changed_history = make_window(historical_close=105.0)
    assert original.symbol == changed_history.symbol
    assert original.as_of == changed_history.as_of
    cache.put(spec, original, 1.0)

    with pytest.raises(KeyError):
        cache.get(spec, changed_history)


def test_same_feature_symbol_and_as_of_with_different_historical_volume_misses() -> None:
    cache = FeatureCache()
    spec = FeatureSpec("current_close", 1)
    original = make_window(historical_volume=1_000)
    changed_history = make_window(historical_volume=9_999)
    assert original.symbol == changed_history.symbol
    assert original.as_of == changed_history.as_of
    cache.put(spec, original, 1.0)

    with pytest.raises(KeyError):
        cache.get(spec, changed_history)


def test_value_equal_separately_constructed_keys_share_cache_entry() -> None:
    cache = FeatureCache()
    original_spec = FeatureSpec("current_close", 2)
    equal_spec = FeatureSpec("current_close", 2)
    original_window = make_window()
    equal_window = make_window()
    assert original_spec is not equal_spec
    assert original_window is not equal_window
    assert original_spec == equal_spec
    assert original_window == equal_window

    cache.put(original_spec, original_window, 102.0)

    assert cache.get(equal_spec, equal_window) == 102.0
    assert len(cache) == 1


def test_registry_and_cache_do_not_compute_or_mutate_inputs() -> None:
    registry = FeatureRegistry()
    cache = FeatureCache()
    feature = _TestFeature("current_close", lookback_bars=2)
    spec_snapshot = FeatureSpec("current_close", 2)
    window = make_window()
    window_snapshot = make_window()

    registry.register(feature)
    cache.put(feature.spec, window, None)

    assert feature.compute_calls == 0
    assert feature.spec == spec_snapshot
    assert window == window_snapshot
    assert registry.get("current_close") is feature
    assert cache.get(spec_snapshot, window_snapshot) is None
