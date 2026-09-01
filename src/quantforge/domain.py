"""Canonical domain objects shared across QuantForge subsystems."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite

__all__ = ["Bar"]


@dataclass(frozen=True, slots=True)
class Bar:
    """An immutable OHLCV observation for one symbol and interval start."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    def __post_init__(self) -> None:
        """Normalize the symbol and reject invalid domain values."""
        if not isinstance(self.symbol, str):
            raise TypeError("symbol must be a string")

        normalized_symbol = self.symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol must not be empty")
        object.__setattr__(self, "symbol", normalized_symbol)

        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        _validate_price("open", self.open)
        _validate_price("high", self.high)
        _validate_price("low", self.low)
        _validate_price("close", self.close)

        if isinstance(self.volume, bool) or not isinstance(self.volume, int):
            raise TypeError("volume must be an integer and must not be boolean")
        if self.volume < 0:
            raise ValueError("volume must be a non-negative integer")

        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to open, close, and high")


def _validate_price(field_name: str, value: float) -> None:
    if not isinstance(value, float):
        raise TypeError(f"{field_name} must be a float")
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be finite and greater than zero")
