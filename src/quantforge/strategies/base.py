"""Immutable, causal contracts for strategy signal generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from re import fullmatch
from typing import Protocol

from quantforge.features import FeatureValue

__all__ = ["Signal", "Strategy", "StrategyContext", "StrategySpec"]

_CANONICAL_NAME_PATTERN = r"[a-z][a-z0-9_]*"


@dataclass(frozen=True, slots=True)
class StrategySpec:
    """Stable metadata and feature requirements for one strategy."""

    name: str
    required_features: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject malformed metadata without normalizing it."""
        _validate_canonical_name(self.name, field_name="strategy name")
        if not isinstance(self.required_features, tuple):
            raise TypeError("required_features must be a tuple of strings")

        seen: set[str] = set()
        for position, feature_name in enumerate(self.required_features, start=1):
            _validate_canonical_name(
                feature_name,
                field_name=f"required feature name at position {position}",
            )
            if feature_name in seen:
                raise ValueError(f"required feature name {feature_name!r} must be unique")
            seen.add(feature_name)


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """Available feature values for one explicit causal evaluation instant."""

    as_of: datetime
    features: tuple[FeatureValue, ...]

    def __post_init__(self) -> None:
        """Enforce timestamp consistency and unambiguous feature inputs."""
        _validate_aware_timestamp(self.as_of, field_name="as_of")
        if not isinstance(self.features, tuple):
            raise TypeError("features must be a tuple of FeatureValue instances")

        seen: set[tuple[str, str]] = set()
        for position, feature in enumerate(self.features, start=1):
            if not isinstance(feature, FeatureValue):
                raise TypeError(
                    f"features must contain only FeatureValue instances; item {position} is invalid"
                )
            if feature.timestamp != self.as_of:
                raise ValueError(
                    f"feature at position {position} must have the same timestamp as as_of"
                )

            key = (feature.feature_name, feature.symbol)
            if key in seen:
                raise ValueError(
                    "features must not contain duplicate (feature_name, symbol) pairs; "
                    f"duplicate {key!r} at position {position}"
                )
            seen.add(key)

    def get(self, feature_name: str, symbol: str) -> float:
        """Return an exact available value or raise ``KeyError`` without normalization."""
        for feature in self.features:
            if feature.feature_name == feature_name and feature.symbol == symbol:
                return feature.value
        raise KeyError((feature_name, symbol))

    @property
    def symbols(self) -> tuple[str, ...]:
        """Return represented symbols in deterministic sorted order."""
        return tuple(sorted({feature.symbol for feature in self.features}))


@dataclass(frozen=True, slots=True)
class Signal:
    """A strategy's finite alpha opinion for one symbol and instant."""

    strategy_name: str
    symbol: str
    timestamp: datetime
    score: float

    def __post_init__(self) -> None:
        """Reject malformed alpha metadata and numeric scores."""
        _validate_canonical_name(self.strategy_name, field_name="strategy name")
        _validate_canonical_symbol(self.symbol)
        _validate_aware_timestamp(self.timestamp, field_name="timestamp")

        if not isinstance(self.score, float):
            raise TypeError("score must be a float")
        if not isfinite(self.score):
            raise ValueError("score must be finite")


class Strategy(Protocol):
    """Structural contract for deterministic causal signal generation."""

    @property
    def spec(self) -> StrategySpec:
        """Return immutable metadata for this strategy."""
        ...

    def generate(self, context: StrategyContext) -> tuple[Signal, ...]:
        """Generate zero or more alpha signals from one causal context."""
        ...


def _validate_canonical_name(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain surrounding whitespace")
    if fullmatch(_CANONICAL_NAME_PATTERN, value) is None:
        raise ValueError(f"{field_name} must match [a-z][a-z0-9_]*")


def _validate_aware_timestamp(value: datetime, *, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _validate_canonical_symbol(symbol: str) -> None:
    if not isinstance(symbol, str):
        raise TypeError("symbol must be a string")
    if not symbol.strip():
        raise ValueError("symbol must not be empty")
    if symbol != symbol.strip().upper():
        raise ValueError("symbol must already be canonical")
