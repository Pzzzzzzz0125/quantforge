"""Immutable execution-intent domain objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite

__all__ = ["Order", "OrderSide", "OrderType"]


class OrderSide(Enum):
    """Explicit direction of requested execution."""

    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Supported execution-intent styles."""

    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True, slots=True)
class Order:
    """Immutable caller-identified intent to buy or sell a positive quantity."""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    timestamp: datetime
    limit_price: float | None = None

    def __post_init__(self) -> None:
        """Validate identity, direction, quantity, time, and type-specific price rules."""
        _validate_order_id(self.order_id)
        _validate_canonical_symbol(self.symbol)

        if not isinstance(self.side, OrderSide):
            raise TypeError("side must be an OrderSide")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int):
            raise TypeError("quantity must be an integer and must not be boolean")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if not isinstance(self.order_type, OrderType):
            raise TypeError("order_type must be an OrderType")

        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        if self.order_type is OrderType.MARKET:
            if self.limit_price is not None:
                raise ValueError("market orders must have limit_price=None")
        else:
            if self.limit_price is None:
                raise ValueError("limit orders require a limit_price")
            if not isinstance(self.limit_price, float):
                raise TypeError("limit_price must be a float")
            if not isfinite(self.limit_price) or self.limit_price <= 0.0:
                raise ValueError("limit_price must be finite and greater than zero")

    @property
    def signed_quantity(self) -> int:
        """Bridge explicit order direction to signed accounting quantity."""
        if self.side is OrderSide.BUY:
            return self.quantity
        return -self.quantity


def _validate_order_id(order_id: str) -> None:
    if not isinstance(order_id, str):
        raise TypeError("order_id must be a string")
    if not order_id.strip():
        raise ValueError("order_id must not be empty")
    if order_id != order_id.strip():
        raise ValueError("order_id must not contain surrounding whitespace")


def _validate_canonical_symbol(symbol: str) -> None:
    if not isinstance(symbol, str):
        raise TypeError("symbol must be a string")
    if not symbol.strip():
        raise ValueError("symbol must not be empty")
    if symbol != symbol.strip().upper():
        raise ValueError("symbol must already be canonical")
