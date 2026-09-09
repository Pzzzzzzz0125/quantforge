"""Immutable, causal contracts for feature computation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from re import fullmatch
from typing import Protocol

from quantforge.domain import Bar

__all__ = ["Feature", "FeatureSpec", "FeatureValue", "FeatureWindow"]

_FEATURE_NAME_PATTERN = r"[a-z][a-z0-9_]*"


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """Stable metadata describing one feature calculation."""

    name: str
    lookback_bars: int

    def __post_init__(self) -> None:
        """Reject invalid metadata without normalizing it."""
        _validate_feature_name(self.name)
        if isinstance(self.lookback_bars, bool) or not isinstance(self.lookback_bars, int):
            raise TypeError("lookback_bars must be an integer and must not be boolean")
        if self.lookback_bars < 1:
            raise ValueError("lookback_bars must be greater than or equal to 1")


@dataclass(frozen=True, slots=True)
class FeatureWindow:
    """An immutable, single-symbol sequence of bars ending at its as-of time."""

    bars: tuple[Bar, ...]

    def __post_init__(self) -> None:
        """Enforce the causal window's type, symbol, and ordering invariants."""
        if not isinstance(self.bars, tuple):
            raise TypeError("bars must be a tuple of Bar instances")
        if not self.bars:
            raise ValueError("bars must contain at least one Bar")

        first = self.bars[0]
        if not isinstance(first, Bar):
            raise TypeError("bars must contain only Bar instances; item 1 is invalid")

        previous_timestamp = first.timestamp
        symbol = first.symbol
        for position, bar in enumerate(self.bars[1:], start=2):
            if not isinstance(bar, Bar):
                raise TypeError(f"bars must contain only Bar instances; item {position} is invalid")
            if bar.symbol != symbol:
                raise ValueError(
                    "bars must contain exactly one symbol; "
                    f"item {position} has symbol {bar.symbol!r}, expected {symbol!r}"
                )
            if bar.timestamp == previous_timestamp:
                raise ValueError(
                    "bar timestamps must be strictly increasing; "
                    f"item {position} duplicates the previous timestamp"
                )
            if bar.timestamp < previous_timestamp:
                raise ValueError(
                    "bar timestamps must be strictly increasing; "
                    f"item {position} is earlier than the previous timestamp"
                )
            previous_timestamp = bar.timestamp

    @property
    def symbol(self) -> str:
        """Return the common canonical symbol."""
        return self.bars[0].symbol

    @property
    def as_of(self) -> datetime:
        """Return the timestamp of the final available bar."""
        return self.current.timestamp

    @property
    def current(self) -> Bar:
        """Return the final available bar."""
        return self.bars[-1]

    @property
    def size(self) -> int:
        """Return the number of bars in the window."""
        return len(self.bars)


@dataclass(frozen=True, slots=True)
class FeatureValue:
    """One available finite feature value at a specific as-of timestamp."""

    feature_name: str
    symbol: str
    timestamp: datetime
    value: float

    def __post_init__(self) -> None:
        """Reject invalid output metadata and numeric values."""
        _validate_feature_name(self.feature_name)
        _validate_canonical_symbol(self.symbol)

        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        if not isinstance(self.value, float):
            raise TypeError("value must be a float")
        if not isfinite(self.value):
            raise ValueError("value must be finite")


class Feature(Protocol):
    """Structural contract for deterministic causal feature calculations."""

    @property
    def spec(self) -> FeatureSpec:
        """Return immutable metadata for this feature."""
        ...

    def compute(self, window: FeatureWindow) -> float | None:
        """Compute from the supplied causal window or return ``None`` during warm-up."""
        ...


def _validate_feature_name(name: str) -> None:
    if not isinstance(name, str):
        raise TypeError("feature name must be a string")
    if not name:
        raise ValueError("feature name must not be empty")
    if name != name.strip():
        raise ValueError("feature name must not contain surrounding whitespace")
    if fullmatch(_FEATURE_NAME_PATTERN, name) is None:
        raise ValueError("feature name must match [a-z][a-z0-9_]*")


def _validate_canonical_symbol(symbol: str) -> None:
    if not isinstance(symbol, str):
        raise TypeError("symbol must be a string")
    if not symbol.strip():
        raise ValueError("symbol must not be empty")
    if symbol != symbol.strip().upper():
        raise ValueError("symbol must already be normalized")
