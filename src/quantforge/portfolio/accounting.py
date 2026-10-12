"""Immutable average-cost portfolio accounting and mark-to-market valuation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isclose, isfinite

__all__ = ["PortfolioState", "PortfolioValuation", "PositionState"]

_RECONCILIATION_TOLERANCE = 1e-12


@dataclass(frozen=True, slots=True)
class PositionState:
    """Immutable signed position state using average-cost accounting."""

    symbol: str
    quantity: int
    average_cost: float | None
    realized_pnl: float

    def __post_init__(self) -> None:
        """Validate the canonical symbol and position accounting invariants."""
        _validate_canonical_symbol(self.symbol)
        _validate_quantity(self.quantity, allow_zero=True)

        if self.quantity == 0:
            if self.average_cost is not None:
                raise ValueError("average_cost must be None for a flat position")
        else:
            if self.average_cost is None:
                raise ValueError("average_cost is required for an open position")
            _validate_positive_float("average_cost", self.average_cost)

        _validate_finite_float("realized_pnl", self.realized_pnl)


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    """Immutable mark-to-market portfolio valuation and P&L reconciliation."""

    initial_cash: float
    cash: float
    market_value: float
    equity: float
    gross_realized_pnl: float
    unrealized_pnl: float
    fees_paid: float
    total_pnl: float

    def __post_init__(self) -> None:
        """Validate finite values and the accounting reconciliation identities."""
        for field_name in (
            "initial_cash",
            "cash",
            "market_value",
            "equity",
            "gross_realized_pnl",
            "unrealized_pnl",
            "fees_paid",
            "total_pnl",
        ):
            _validate_finite_float(field_name, getattr(self, field_name))

        if self.initial_cash < 0.0:
            raise ValueError("initial_cash must be greater than or equal to zero")
        if self.fees_paid < 0.0:
            raise ValueError("fees_paid must be greater than or equal to zero")
        if not _approximately_equal(self.equity, self.cash + self.market_value):
            raise ValueError("equity must equal cash plus market_value")
        if not _approximately_equal(self.total_pnl, self.equity - self.initial_cash):
            raise ValueError("total_pnl must equal equity minus initial_cash")

        reconciled_pnl = self.gross_realized_pnl + self.unrealized_pnl - self.fees_paid
        if not _approximately_equal(self.total_pnl, reconciled_pnl):
            raise ValueError(
                "total_pnl must reconcile with gross_realized_pnl plus "
                "unrealized_pnl minus fees_paid"
            )


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """Immutable portfolio accounting snapshot."""

    initial_cash: float
    cash: float
    positions: tuple[PositionState, ...]
    fees_paid: float

    def __post_init__(self) -> None:
        """Validate monetary values and deterministic position storage."""
        _validate_finite_float("initial_cash", self.initial_cash)
        if self.initial_cash < 0.0:
            raise ValueError("initial_cash must be greater than or equal to zero")
        _validate_finite_float("cash", self.cash)
        _validate_nonnegative_float("fees_paid", self.fees_paid)

        if not isinstance(self.positions, tuple):
            raise TypeError("positions must be a tuple of PositionState instances")

        symbols: list[str] = []
        for position, position_state in enumerate(self.positions, start=1):
            if not isinstance(position_state, PositionState):
                raise TypeError(
                    "positions must contain only PositionState instances; "
                    f"item {position} is invalid"
                )
            symbols.append(position_state.symbol)

        if len(symbols) != len(set(symbols)):
            raise ValueError("positions must not contain duplicate symbols")
        if symbols != sorted(symbols):
            raise ValueError("positions must be ordered by symbol")

    @classmethod
    def starting(cls, initial_cash: float) -> PortfolioState:
        """Create a flat starting portfolio with no fees or positions."""
        return cls(
            initial_cash=initial_cash,
            cash=initial_cash,
            positions=(),
            fees_paid=0.0,
        )

    def get_position(self, symbol: str) -> PositionState | None:
        """Return an exact-symbol position record when one exists."""
        for position in self.positions:
            if position.symbol == symbol:
                return position
        return None

    @property
    def active_positions(self) -> tuple[PositionState, ...]:
        """Return non-flat positions in deterministic symbol order."""
        return tuple(position for position in self.positions if position.quantity != 0)

    @property
    def gross_realized_pnl(self) -> float:
        """Return cumulative realized trading P&L before fees."""
        return sum((position.realized_pnl for position in self.positions), start=0.0)

    def apply_fill(
        self,
        *,
        symbol: str,
        quantity: int,
        price: float,
        fee: float,
    ) -> PortfolioState:
        """Account for supplied executed-trade facts and return a new snapshot."""
        _validate_canonical_symbol(symbol)
        _validate_quantity(quantity, allow_zero=False)
        _validate_positive_float("price", price)
        _validate_nonnegative_float("fee", fee)

        existing = self.get_position(symbol)
        if existing is None:
            existing = PositionState(
                symbol=symbol,
                quantity=0,
                average_cost=None,
                realized_pnl=0.0,
            )

        updated = _apply_position_fill(existing, quantity=quantity, price=price)
        updated_positions = [
            updated if position.symbol == symbol else position for position in self.positions
        ]
        if self.get_position(symbol) is None:
            updated_positions.append(updated)
        updated_positions.sort(key=lambda position: position.symbol)

        cash_delta = -(quantity * price) - fee
        return PortfolioState(
            initial_cash=self.initial_cash,
            cash=self.cash + cash_delta,
            positions=tuple(updated_positions),
            fees_paid=self.fees_paid + fee,
        )

    def value(self, marks: Mapping[str, float]) -> PortfolioValuation:
        """Value all open positions with exact-symbol caller-supplied marks."""
        if not isinstance(marks, Mapping):
            raise TypeError("marks must be a mapping from symbols to floats")

        market_value = 0.0
        unrealized_pnl = 0.0
        for position in self.active_positions:
            try:
                mark = marks[position.symbol]
            except KeyError:
                raise KeyError(f"missing mark for open position {position.symbol!r}") from None
            _validate_positive_float(f"mark for {position.symbol}", mark)

            average_cost = position.average_cost
            assert average_cost is not None
            market_value += position.quantity * mark
            unrealized_pnl += position.quantity * (mark - average_cost)

        equity = self.cash + market_value
        total_pnl = equity - self.initial_cash
        return PortfolioValuation(
            initial_cash=self.initial_cash,
            cash=self.cash,
            market_value=market_value,
            equity=equity,
            gross_realized_pnl=self.gross_realized_pnl,
            unrealized_pnl=unrealized_pnl,
            fees_paid=self.fees_paid,
            total_pnl=total_pnl,
        )


def _apply_position_fill(
    position: PositionState,
    *,
    quantity: int,
    price: float,
) -> PositionState:
    existing_quantity = position.quantity
    new_quantity = existing_quantity + quantity
    average_cost = position.average_cost
    realized_pnl = position.realized_pnl

    if existing_quantity == 0:
        new_average_cost: float | None = price
    elif (existing_quantity > 0) == (quantity > 0):
        assert average_cost is not None
        new_average_cost = (abs(existing_quantity) * average_cost + abs(quantity) * price) / abs(
            new_quantity
        )
    else:
        assert average_cost is not None
        closed_quantity = min(abs(existing_quantity), abs(quantity))
        existing_sign = 1 if existing_quantity > 0 else -1
        realized_pnl += closed_quantity * (price - average_cost) * existing_sign

        if new_quantity == 0:
            new_average_cost = None
        elif (new_quantity > 0) == (existing_quantity > 0):
            new_average_cost = average_cost
        else:
            new_average_cost = price

    return PositionState(
        symbol=position.symbol,
        quantity=new_quantity,
        average_cost=new_average_cost,
        realized_pnl=realized_pnl,
    )


def _validate_canonical_symbol(symbol: str) -> None:
    if not isinstance(symbol, str):
        raise TypeError("symbol must be a string")
    if not symbol.strip():
        raise ValueError("symbol must not be empty")
    if symbol != symbol.strip().upper():
        raise ValueError("symbol must already be canonical")


def _validate_quantity(quantity: int, *, allow_zero: bool) -> None:
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise TypeError("quantity must be an integer and must not be boolean")
    if not allow_zero and quantity == 0:
        raise ValueError("fill quantity must not be zero")


def _validate_finite_float(field_name: str, value: float) -> None:
    if not isinstance(value, float):
        raise TypeError(f"{field_name} must be a float")
    if not isfinite(value):
        raise ValueError(f"{field_name} must be finite")


def _validate_positive_float(field_name: str, value: float) -> None:
    _validate_finite_float(field_name, value)
    if value <= 0.0:
        raise ValueError(f"{field_name} must be greater than zero")


def _validate_nonnegative_float(field_name: str, value: float) -> None:
    _validate_finite_float(field_name, value)
    if value < 0.0:
        raise ValueError(f"{field_name} must be greater than or equal to zero")


def _approximately_equal(left: float, right: float) -> bool:
    return isclose(
        left,
        right,
        rel_tol=_RECONCILIATION_TOLERANCE,
        abs_tol=_RECONCILIATION_TOLERANCE,
    )
