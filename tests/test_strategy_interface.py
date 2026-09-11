"""Tests for the immutable causal strategy-domain contracts."""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from math import inf, nan

import pytest

from quantforge.features import FeatureValue
from quantforge.strategies import Signal, Strategy, StrategyContext, StrategySpec

AS_OF = datetime(2026, 9, 9, 20, 0, tzinfo=UTC)


class _NoOffsetTimezone(tzinfo):
    def utcoffset(self, dt: datetime | None) -> None:
        return None

    def dst(self, dt: datetime | None) -> None:
        return None

    def tzname(self, dt: datetime | None) -> str:
        return "NO_OFFSET"


class _TestScoreStrategy:
    def __init__(self) -> None:
        self._spec = StrategySpec(
            name="test_score_strategy",
            required_features=("alpha_score",),
        )

    @property
    def spec(self) -> StrategySpec:
        return self._spec

    def generate(self, context: StrategyContext) -> tuple[Signal, ...]:
        signals: list[Signal] = []
        for symbol in context.symbols:
            try:
                score = context.get("alpha_score", symbol)
            except KeyError:
                continue
            signals.append(
                Signal(
                    strategy_name=self.spec.name,
                    symbol=symbol,
                    timestamp=context.as_of,
                    score=score,
                )
            )
        return tuple(signals)


def make_feature_value(
    feature_name: str = "alpha_score",
    symbol: str = "AAPL",
    *,
    timestamp: datetime = AS_OF,
    value: float = 1.5,
) -> FeatureValue:
    return FeatureValue(
        feature_name=feature_name,
        symbol=symbol,
        timestamp=timestamp,
        value=value,
    )


def make_signal(**overrides: object) -> Signal:
    values: dict[str, object] = {
        "strategy_name": "test_strategy",
        "symbol": "AAPL",
        "timestamp": AS_OF,
        "score": 1.5,
    }
    values.update(overrides)
    return Signal(**values)  # type: ignore[arg-type]


def test_strategy_spec_preserves_valid_metadata_and_required_feature_order() -> None:
    spec = StrategySpec(
        name="cross_sectional_strategy",
        required_features=("momentum_20", "volatility_20"),
    )

    assert tuple(field.name for field in fields(StrategySpec)) == (
        "name",
        "required_features",
    )
    assert spec.name == "cross_sectional_strategy"
    assert spec.required_features == ("momentum_20", "volatility_20")
    assert isinstance(spec.required_features, tuple)
    assert not hasattr(spec, "__dict__")


def test_strategy_spec_accepts_no_required_features() -> None:
    assert StrategySpec("no_inputs", ()).required_features == ()


@pytest.mark.parametrize("name", ["", " ", " test_strategy", "test_strategy "])
def test_strategy_spec_rejects_empty_or_whitespace_name(name: str) -> None:
    with pytest.raises(ValueError, match="strategy name"):
        StrategySpec(name, ())


@pytest.mark.parametrize("name", ["TestStrategy", "1_strategy", "test-strategy"])
def test_strategy_spec_rejects_noncanonical_name(name: str) -> None:
    with pytest.raises(ValueError, match=r"\[a-z\]\[a-z0-9_\]\*"):
        StrategySpec(name, ())


def test_strategy_spec_rejects_non_string_name() -> None:
    with pytest.raises(TypeError, match="strategy name must be a string"):
        StrategySpec(1, ())  # type: ignore[arg-type]


def test_strategy_spec_requires_feature_tuple() -> None:
    with pytest.raises(TypeError, match="required_features must be a tuple"):
        StrategySpec("test_strategy", ["alpha_score"])  # type: ignore[arg-type]


@pytest.mark.parametrize("feature_name", ["AlphaScore", " alpha_score", "alpha-score"])
def test_strategy_spec_rejects_invalid_required_feature_name(feature_name: str) -> None:
    with pytest.raises(ValueError, match="required feature name"):
        StrategySpec("test_strategy", (feature_name,))


def test_strategy_spec_rejects_non_string_required_feature_name() -> None:
    with pytest.raises(TypeError, match="required feature name"):
        StrategySpec("test_strategy", (1,))  # type: ignore[arg-type]


def test_strategy_spec_rejects_duplicate_required_features() -> None:
    with pytest.raises(ValueError, match="required feature name 'alpha_score' must be unique"):
        StrategySpec("test_strategy", ("alpha_score", "alpha_score"))


def test_strategy_spec_is_immutable_and_hashable() -> None:
    spec = StrategySpec("test_strategy", ("alpha_score",))

    with pytest.raises(FrozenInstanceError):
        spec.name = "other"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        spec.required_features = ()  # type: ignore[misc]
    assert {spec: "registered"}[spec] == "registered"


def test_empty_strategy_context_is_valid() -> None:
    context = StrategyContext(as_of=AS_OF, features=())

    assert tuple(field.name for field in fields(StrategyContext)) == ("as_of", "features")
    assert context.features == ()
    assert context.symbols == ()
    assert not hasattr(context, "__dict__")


def test_context_supports_multiple_features_and_symbols() -> None:
    context = StrategyContext(
        as_of=AS_OF,
        features=(
            make_feature_value("volatility_20", "MSFT", value=0.2),
            make_feature_value("alpha_score", "AAPL", value=2.0),
            make_feature_value("alpha_score", "MSFT", value=-1.0),
        ),
    )

    assert context.features[0].feature_name == "volatility_20"
    assert context.symbols == ("AAPL", "MSFT")
    assert context.get("alpha_score", "AAPL") == 2.0
    assert context.get("alpha_score", "MSFT") == -1.0
    assert context.get("volatility_20", "MSFT") == 0.2


def test_context_requires_timezone_aware_as_of() -> None:
    with pytest.raises(ValueError, match="as_of must be timezone-aware"):
        StrategyContext(datetime(2026, 9, 9, 20, 0), ())


def test_context_rejects_as_of_whose_timezone_has_no_utc_offset() -> None:
    with pytest.raises(ValueError, match="as_of must be timezone-aware"):
        StrategyContext(datetime(2026, 9, 9, tzinfo=_NoOffsetTimezone()), ())


def test_context_rejects_non_datetime_as_of() -> None:
    with pytest.raises(TypeError, match="as_of must be a datetime"):
        StrategyContext("2026-09-09T20:00:00Z", ())  # type: ignore[arg-type]


def test_context_requires_feature_tuple() -> None:
    with pytest.raises(TypeError, match="features must be a tuple"):
        StrategyContext(AS_OF, [make_feature_value()])  # type: ignore[arg-type]


@pytest.mark.parametrize("position", [0, 1])
def test_context_rejects_non_feature_value(position: int) -> None:
    feature_values: tuple[object, ...] = (
        make_feature_value("first_feature"),
        make_feature_value("second_feature"),
    )
    invalid = feature_values[:position] + ("not-a-feature-value",) + feature_values[position + 1 :]

    with pytest.raises(TypeError, match="only FeatureValue instances"):
        StrategyContext(AS_OF, invalid)  # type: ignore[arg-type]


@pytest.mark.parametrize("delta", [timedelta(seconds=-1), timedelta(seconds=1)])
def test_context_rejects_feature_timestamp_before_or_after_as_of(delta: timedelta) -> None:
    feature = make_feature_value(timestamp=AS_OF + delta)

    with pytest.raises(ValueError, match="same timestamp as as_of"):
        StrategyContext(AS_OF, (feature,))


def test_context_accepts_equivalent_instant_with_different_timezone_offset() -> None:
    pacific = timezone(timedelta(hours=-7))
    equivalent_timestamp = AS_OF.astimezone(pacific)
    assert equivalent_timestamp is not AS_OF
    assert equivalent_timestamp == AS_OF

    context = StrategyContext(
        as_of=AS_OF,
        features=(make_feature_value(timestamp=equivalent_timestamp),),
    )

    assert context.features[0].timestamp is equivalent_timestamp


def test_context_rejects_duplicate_feature_and_symbol_pair() -> None:
    duplicate_key_features = (
        make_feature_value(value=1.0),
        make_feature_value(value=2.0),
    )

    with pytest.raises(ValueError, match=r"duplicate \(feature_name, symbol\) pairs"):
        StrategyContext(AS_OF, duplicate_key_features)


def test_context_allows_same_feature_for_different_symbols_and_different_features_per_symbol() -> (
    None
):
    context = StrategyContext(
        AS_OF,
        (
            make_feature_value("alpha_score", "AAPL"),
            make_feature_value("alpha_score", "MSFT"),
            make_feature_value("volatility_20", "AAPL"),
        ),
    )

    assert context.symbols == ("AAPL", "MSFT")


@pytest.mark.parametrize(
    ("feature_name", "symbol"),
    [
        ("missing_feature", "AAPL"),
        ("alpha_score", "MSFT"),
        (" alpha_score ", "AAPL"),
        ("ALPHA_SCORE", "AAPL"),
        ("alpha_score", "aapl"),
        ("alpha_score", " AAPL "),
    ],
)
def test_context_lookup_miss_or_noncanonical_input_raises_key_error(
    feature_name: str,
    symbol: str,
) -> None:
    context = StrategyContext(AS_OF, (make_feature_value(),))

    with pytest.raises(KeyError):
        context.get(feature_name, symbol)

    assert context.get("alpha_score", "AAPL") == 1.5


def test_context_is_immutable_and_hashable() -> None:
    context = StrategyContext(AS_OF, (make_feature_value(),))

    with pytest.raises(FrozenInstanceError):
        context.as_of = AS_OF + timedelta(days=1)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        context.features = ()  # type: ignore[misc]
    assert {context: "evaluated"}[context] == "evaluated"


@pytest.mark.parametrize("score", [3.5, -4.0, 0.0, 100.0, -100.0])
def test_signal_accepts_any_finite_float_score(score: float) -> None:
    signal = make_signal(score=score)

    assert tuple(field.name for field in fields(Signal)) == (
        "strategy_name",
        "symbol",
        "timestamp",
        "score",
    )
    assert signal.score == score
    assert not hasattr(signal, "__dict__")


@pytest.mark.parametrize("strategy_name", ["", " ", "TestStrategy", " test_strategy"])
def test_signal_rejects_invalid_strategy_name(strategy_name: str) -> None:
    with pytest.raises(ValueError, match="strategy name"):
        make_signal(strategy_name=strategy_name)


def test_signal_rejects_non_string_strategy_name() -> None:
    with pytest.raises(TypeError, match="strategy name must be a string"):
        make_signal(strategy_name=1)


@pytest.mark.parametrize("symbol", ["", " ", "aapl", " AAPL "])
def test_signal_rejects_noncanonical_symbol(symbol: str) -> None:
    with pytest.raises(ValueError, match="symbol"):
        make_signal(symbol=symbol)


def test_signal_rejects_non_string_symbol() -> None:
    with pytest.raises(TypeError, match="symbol must be a string"):
        make_signal(symbol=1)


@pytest.mark.parametrize(
    "timestamp",
    [datetime(2026, 9, 9, 20, 0), datetime(2026, 9, 9, tzinfo=_NoOffsetTimezone())],
)
def test_signal_rejects_timestamp_without_utc_offset(timestamp: datetime) -> None:
    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        make_signal(timestamp=timestamp)


def test_signal_rejects_non_datetime_timestamp() -> None:
    with pytest.raises(TypeError, match="timestamp must be a datetime"):
        make_signal(timestamp="2026-09-09T20:00:00Z")


@pytest.mark.parametrize("score", [1, 0, True])
def test_signal_rejects_integer_and_boolean_score(score: object) -> None:
    with pytest.raises(TypeError, match="score must be a float"):
        make_signal(score=score)


@pytest.mark.parametrize("score", [nan, inf, -inf])
def test_signal_rejects_non_finite_score(score: float) -> None:
    with pytest.raises(ValueError, match="score must be finite"):
        make_signal(score=score)


def test_signal_is_immutable_hashable_and_contains_no_downstream_fields() -> None:
    signal = make_signal()

    with pytest.raises(FrozenInstanceError):
        signal.score = 2.0  # type: ignore[misc]
    assert {signal: "opinion"}[signal] == "opinion"
    assert tuple(field.name for field in fields(Signal)) == (
        "strategy_name",
        "symbol",
        "timestamp",
        "score",
    )
    for excluded in (
        "quantity",
        "shares",
        "notional",
        "target_weight",
        "limit_price",
        "order_type",
        "fill_price",
        "commission",
        "slippage",
        "cash",
        "position",
    ):
        assert not hasattr(signal, excluded)


def generate_as_strategy(strategy: Strategy, context: StrategyContext) -> tuple[Signal, ...]:
    """Exercise static structural compatibility with the public protocol."""
    return strategy.generate(context)


def test_test_only_strategy_supports_empty_signal_output() -> None:
    strategy = _TestScoreStrategy()
    context = StrategyContext(AS_OF, ())

    assert generate_as_strategy(strategy, context) == ()


def test_test_only_strategy_emits_deterministic_multi_symbol_signals_at_context_time() -> None:
    strategy = _TestScoreStrategy()
    context = StrategyContext(
        AS_OF,
        (
            make_feature_value(symbol="MSFT", value=-2.5),
            make_feature_value(symbol="AAPL", value=3.0),
        ),
    )
    context_snapshot = StrategyContext(AS_OF, tuple(context.features))

    first = generate_as_strategy(strategy, context)
    second = generate_as_strategy(strategy, context)

    assert first == second
    assert isinstance(first, tuple)
    assert tuple(signal.symbol for signal in first) == ("AAPL", "MSFT")
    assert tuple(signal.score for signal in first) == (3.0, -2.5)
    assert all(signal.strategy_name == strategy.spec.name for signal in first)
    assert all(signal.timestamp == context.as_of for signal in first)
    assert context == context_snapshot


def test_strategy_context_exposes_no_dataset_portfolio_order_or_execution_state() -> None:
    context = StrategyContext(AS_OF, ())

    assert tuple(field.name for field in fields(StrategyContext)) == ("as_of", "features")
    for excluded in (
        "dataset",
        "index",
        "provider",
        "store",
        "portfolio",
        "cash",
        "positions",
        "orders",
        "fills",
        "execution",
    ):
        assert not hasattr(context, excluded)
