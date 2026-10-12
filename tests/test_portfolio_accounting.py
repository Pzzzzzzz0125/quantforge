"""Deterministic tests for signed average-cost portfolio accounting."""

from dataclasses import FrozenInstanceError, fields
from math import inf, nan

import pytest

import quantforge.portfolio as portfolio_module
from quantforge.portfolio import PortfolioState, PortfolioValuation, PositionState

INITIAL_CASH = 100_000.0


def starting(cash: float = INITIAL_CASH) -> PortfolioState:
    return PortfolioState.starting(initial_cash=cash)


def execute(
    state: PortfolioState,
    symbol: str,
    quantity: int,
    price: float,
    fee: float = 0.0,
) -> PortfolioState:
    return state.apply_fill(symbol=symbol, quantity=quantity, price=price, fee=fee)


def assert_reconciled(valuation: PortfolioValuation) -> None:
    assert valuation.equity == pytest.approx(
        valuation.cash + valuation.market_value,
        rel=1e-12,
        abs=1e-12,
    )
    assert valuation.total_pnl == pytest.approx(
        valuation.equity - valuation.initial_cash,
        rel=1e-12,
        abs=1e-12,
    )
    assert valuation.total_pnl == pytest.approx(
        valuation.gross_realized_pnl + valuation.unrealized_pnl - valuation.fees_paid,
        rel=1e-12,
        abs=1e-12,
    )


@pytest.mark.parametrize(
    ("quantity", "average_cost"),
    [(100, 50.0), (-100, 50.0), (0, None)],
)
def test_position_state_supports_long_short_and_flat_quantities(
    quantity: int,
    average_cost: float | None,
) -> None:
    position = PositionState("AAPL", quantity, average_cost, 0.0)

    assert tuple(field.name for field in fields(PositionState)) == (
        "symbol",
        "quantity",
        "average_cost",
        "realized_pnl",
    )
    assert position.quantity == quantity
    assert position.average_cost == average_cost
    assert not hasattr(position, "__dict__")


@pytest.mark.parametrize("symbol", ["", " ", "aapl", " AAPL "])
def test_position_state_rejects_noncanonical_symbol(symbol: str) -> None:
    with pytest.raises(ValueError, match="symbol"):
        PositionState(symbol, 1, 50.0, 0.0)


def test_position_state_rejects_non_string_symbol() -> None:
    with pytest.raises(TypeError, match="symbol must be a string"):
        PositionState(1, 1, 50.0, 0.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("quantity", [True, 1.0])
def test_position_state_rejects_non_integer_or_boolean_quantity(quantity: object) -> None:
    with pytest.raises(TypeError, match="quantity must be an integer"):
        PositionState("AAPL", quantity, 50.0, 0.0)  # type: ignore[arg-type]


def test_flat_position_requires_no_average_cost() -> None:
    with pytest.raises(ValueError, match="average_cost must be None"):
        PositionState("AAPL", 0, 50.0, 0.0)


def test_open_position_requires_average_cost() -> None:
    with pytest.raises(ValueError, match="average_cost is required"):
        PositionState("AAPL", 1, None, 0.0)


@pytest.mark.parametrize("average_cost", [0.0, -1.0, nan, inf, -inf])
def test_open_position_rejects_nonpositive_or_nonfinite_average_cost(
    average_cost: float,
) -> None:
    with pytest.raises(ValueError, match="average_cost"):
        PositionState("AAPL", 1, average_cost, 0.0)


@pytest.mark.parametrize("average_cost", [50, True])
def test_open_position_rejects_non_float_average_cost(average_cost: object) -> None:
    with pytest.raises(TypeError, match="average_cost must be a float"):
        PositionState("AAPL", 1, average_cost, 0.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("realized_pnl", [nan, inf, -inf])
def test_position_state_rejects_nonfinite_realized_pnl(realized_pnl: float) -> None:
    with pytest.raises(ValueError, match="realized_pnl must be finite"):
        PositionState("AAPL", 1, 50.0, realized_pnl)


def test_position_state_rejects_non_float_realized_pnl() -> None:
    with pytest.raises(TypeError, match="realized_pnl must be a float"):
        PositionState("AAPL", 1, 50.0, 0)


def test_position_state_is_immutable_and_hashable() -> None:
    position = PositionState("AAPL", 100, 50.0, 25.0)

    with pytest.raises(FrozenInstanceError):
        position.quantity = 200  # type: ignore[misc]
    assert {position: "held"}[position] == "held"


def test_starting_portfolio_has_exact_initial_state() -> None:
    state = starting()

    assert tuple(field.name for field in fields(PortfolioState)) == (
        "initial_cash",
        "cash",
        "positions",
        "fees_paid",
    )
    assert state == PortfolioState(INITIAL_CASH, INITIAL_CASH, (), 0.0)
    assert state.active_positions == ()
    assert state.gross_realized_pnl == 0.0
    assert not hasattr(state, "__dict__")


@pytest.mark.parametrize("initial_cash", [-1.0, nan, inf, -inf])
def test_starting_portfolio_rejects_invalid_initial_cash(initial_cash: float) -> None:
    with pytest.raises(ValueError, match="initial_cash"):
        starting(initial_cash)


def test_starting_portfolio_requires_float_initial_cash() -> None:
    with pytest.raises(TypeError, match="initial_cash must be a float"):
        PortfolioState.starting(100_000)


@pytest.mark.parametrize("cash", [nan, inf, -inf])
def test_portfolio_state_rejects_nonfinite_current_cash(cash: float) -> None:
    with pytest.raises(ValueError, match="cash must be finite"):
        PortfolioState(INITIAL_CASH, cash, (), 0.0)


def test_portfolio_state_allows_negative_cash() -> None:
    state = execute(starting(1.0), "AAPL", 1, 50.0)

    assert state.cash == -49.0


@pytest.mark.parametrize("fees_paid", [-1.0, nan, inf, -inf])
def test_portfolio_state_rejects_invalid_fees_paid(fees_paid: float) -> None:
    with pytest.raises(ValueError, match="fees_paid"):
        PortfolioState(INITIAL_CASH, INITIAL_CASH, (), fees_paid)


def test_portfolio_state_requires_float_cash_and_fees() -> None:
    with pytest.raises(TypeError, match="cash must be a float"):
        PortfolioState(INITIAL_CASH, 100_000, (), 0.0)
    with pytest.raises(TypeError, match="fees_paid must be a float"):
        PortfolioState(INITIAL_CASH, INITIAL_CASH, (), 0)


def test_portfolio_state_requires_position_tuple() -> None:
    with pytest.raises(TypeError, match="positions must be a tuple"):
        PortfolioState(INITIAL_CASH, INITIAL_CASH, [], 0.0)  # type: ignore[arg-type]


def test_portfolio_state_rejects_non_position_element() -> None:
    with pytest.raises(TypeError, match="only PositionState instances"):
        PortfolioState(INITIAL_CASH, INITIAL_CASH, ("AAPL",), 0.0)  # type: ignore[arg-type]


def test_portfolio_state_rejects_duplicate_position_symbols() -> None:
    position = PositionState("AAPL", 1, 50.0, 0.0)

    with pytest.raises(ValueError, match="duplicate symbols"):
        PortfolioState(INITIAL_CASH, INITIAL_CASH, (position, position), 0.0)


def test_portfolio_state_requires_deterministic_symbol_order() -> None:
    positions = (
        PositionState("MSFT", 1, 50.0, 0.0),
        PositionState("AAPL", 1, 50.0, 0.0),
    )

    with pytest.raises(ValueError, match="ordered by symbol"):
        PortfolioState(INITIAL_CASH, INITIAL_CASH, positions, 0.0)


def test_position_lookup_is_exact_and_active_positions_exclude_flat_history() -> None:
    flat = PositionState("AAPL", 0, None, 100.0)
    active = PositionState("MSFT", -10, 50.0, 25.0)
    state = PortfolioState(INITIAL_CASH, INITIAL_CASH, (flat, active), 0.0)

    assert state.get_position("AAPL") is flat
    assert state.get_position("MSFT") is active
    assert state.get_position("msft") is None
    assert state.get_position(" MSFT ") is None
    assert state.get_position("NVDA") is None
    assert state.active_positions == (active,)
    assert state.gross_realized_pnl == 125.0


def test_portfolio_state_is_immutable_and_hashable() -> None:
    state = starting()

    with pytest.raises(FrozenInstanceError):
        state.cash = 0.0  # type: ignore[misc]
    assert {state: "snapshot"}[state] == "snapshot"


@pytest.mark.parametrize("symbol", ["", " ", "aapl", " AAPL "])
def test_apply_fill_rejects_noncanonical_symbol(symbol: str) -> None:
    with pytest.raises(ValueError, match="symbol"):
        execute(starting(), symbol, 1, 50.0)


@pytest.mark.parametrize("quantity", [True, 1.5])
def test_apply_fill_rejects_noninteger_or_boolean_quantity(quantity: object) -> None:
    with pytest.raises(TypeError, match="quantity must be an integer"):
        starting().apply_fill(
            symbol="AAPL",
            quantity=quantity,  # type: ignore[arg-type]
            price=50.0,
            fee=0.0,
        )


def test_apply_fill_rejects_zero_quantity() -> None:
    with pytest.raises(ValueError, match="fill quantity must not be zero"):
        execute(starting(), "AAPL", 0, 50.0)


@pytest.mark.parametrize("price", [0.0, -1.0, nan, inf, -inf])
def test_apply_fill_rejects_nonpositive_or_nonfinite_price(price: float) -> None:
    with pytest.raises(ValueError, match="price"):
        execute(starting(), "AAPL", 1, price)


@pytest.mark.parametrize("price", [50, True])
def test_apply_fill_rejects_nonfloat_price(price: object) -> None:
    with pytest.raises(TypeError, match="price must be a float"):
        starting().apply_fill(
            symbol="AAPL",
            quantity=1,
            price=price,  # type: ignore[arg-type]
            fee=0.0,
        )


@pytest.mark.parametrize("fee", [-1.0, nan, inf, -inf])
def test_apply_fill_rejects_negative_or_nonfinite_fee(fee: float) -> None:
    with pytest.raises(ValueError, match="fee"):
        execute(starting(), "AAPL", 1, 50.0, fee)


@pytest.mark.parametrize("fee", [1, True])
def test_apply_fill_rejects_nonfloat_fee(fee: object) -> None:
    with pytest.raises(TypeError, match="fee must be a float"):
        starting().apply_fill(
            symbol="AAPL",
            quantity=1,
            price=50.0,
            fee=fee,  # type: ignore[arg-type]
        )


def test_scenario_a_open_long_marked_at_cost() -> None:
    state = execute(starting(), "AAPL", 100, 50.0)
    valuation = state.value({"AAPL": 50.0})

    assert state.cash == 95_000.0
    assert state.get_position("AAPL") == PositionState("AAPL", 100, 50.0, 0.0)
    assert valuation.market_value == 5_000.0
    assert valuation.equity == 100_000.0
    assert valuation.unrealized_pnl == 0.0
    assert valuation.total_pnl == 0.0
    assert_reconciled(valuation)


def test_scenario_b_long_marked_above_cost() -> None:
    state = execute(starting(), "AAPL", 100, 50.0)
    valuation = state.value({"AAPL": 60.0})

    assert state.cash == 95_000.0
    assert valuation.market_value == 6_000.0
    assert valuation.equity == 101_000.0
    assert valuation.unrealized_pnl == 1_000.0
    assert valuation.total_pnl == 1_000.0
    assert_reconciled(valuation)


def test_scenario_c_short_marked_below_cost() -> None:
    state = execute(starting(), "AAPL", -100, 50.0)
    valuation = state.value({"AAPL": 40.0})

    assert state.cash == 105_000.0
    assert state.get_position("AAPL") == PositionState("AAPL", -100, 50.0, 0.0)
    assert valuation.market_value == -4_000.0
    assert valuation.equity == 101_000.0
    assert valuation.unrealized_pnl == 1_000.0
    assert valuation.total_pnl == 1_000.0
    assert_reconciled(valuation)


def test_scenario_d_increasing_long_uses_weighted_average_cost() -> None:
    first = execute(starting(), "AAPL", 100, 50.0)
    second = execute(first, "AAPL", 100, 60.0)

    assert second.get_position("AAPL") == PositionState("AAPL", 200, 55.0, 0.0)
    assert second.cash == 89_000.0


def test_increasing_short_uses_weighted_average_cost() -> None:
    first = execute(starting(), "AAPL", -100, 50.0)
    second = execute(first, "AAPL", -100, 60.0)

    assert second.get_position("AAPL") == PositionState("AAPL", -200, 55.0, 0.0)
    assert second.cash == 111_000.0


@pytest.mark.parametrize(
    ("exit_price", "expected_realized"),
    [(60.0, 400.0), (40.0, -400.0)],
)
def test_partial_long_reduction_preserves_average_cost(
    exit_price: float,
    expected_realized: float,
) -> None:
    opened = execute(starting(), "AAPL", 100, 50.0)
    reduced = execute(opened, "AAPL", -40, exit_price)

    assert reduced.get_position("AAPL") == PositionState("AAPL", 60, 50.0, expected_realized)


@pytest.mark.parametrize(
    ("cover_price", "expected_realized"),
    [(40.0, 400.0), (60.0, -400.0)],
)
def test_partial_short_cover_preserves_average_cost(
    cover_price: float,
    expected_realized: float,
) -> None:
    opened = execute(starting(), "AAPL", -100, 50.0)
    reduced = execute(opened, "AAPL", 40, cover_price)

    assert reduced.get_position("AAPL") == PositionState("AAPL", -60, 50.0, expected_realized)


@pytest.mark.parametrize(
    ("exit_price", "expected_realized", "expected_cash"),
    [(60.0, 1_000.0, 101_000.0), (40.0, -1_000.0, 99_000.0)],
)
def test_full_long_close_sets_flat_average_cost_none(
    exit_price: float,
    expected_realized: float,
    expected_cash: float,
) -> None:
    opened = execute(starting(), "AAPL", 100, 50.0)
    closed = execute(opened, "AAPL", -100, exit_price)

    assert closed.get_position("AAPL") == PositionState("AAPL", 0, None, expected_realized)
    assert closed.cash == expected_cash
    assert closed.active_positions == ()


@pytest.mark.parametrize(
    ("cover_price", "expected_realized", "expected_cash"),
    [(40.0, 1_000.0, 101_000.0), (60.0, -1_000.0, 99_000.0)],
)
def test_full_short_close_sets_flat_average_cost_none(
    cover_price: float,
    expected_realized: float,
    expected_cash: float,
) -> None:
    opened = execute(starting(), "AAPL", -100, 50.0)
    closed = execute(opened, "AAPL", 100, cover_price)

    assert closed.get_position("AAPL") == PositionState("AAPL", 0, None, expected_realized)
    assert closed.cash == expected_cash
    assert closed.active_positions == ()


def test_scenario_e_long_to_short_reversal_uses_execution_price_for_residual() -> None:
    long_state = execute(starting(), "AAPL", 100, 50.0)
    reversed_state = execute(long_state, "AAPL", -150, 60.0)

    assert reversed_state.get_position("AAPL") == PositionState("AAPL", -50, 60.0, 1_000.0)
    assert reversed_state.cash == 104_000.0
    assert reversed_state.gross_realized_pnl == 1_000.0
    assert_reconciled(reversed_state.value({"AAPL": 60.0}))


def test_short_to_long_reversal_uses_execution_price_for_residual() -> None:
    short_state = execute(starting(), "AAPL", -100, 50.0)
    reversed_state = execute(short_state, "AAPL", 150, 40.0)

    assert reversed_state.get_position("AAPL") == PositionState("AAPL", 50, 40.0, 1_000.0)
    assert reversed_state.cash == 99_000.0
    assert reversed_state.gross_realized_pnl == 1_000.0
    assert_reconciled(reversed_state.value({"AAPL": 40.0}))


def test_cash_delta_and_fees_are_explicit_and_separate_from_gross_realized_pnl() -> None:
    bought = execute(starting(), "AAPL", 100, 50.0, fee=2.0)
    sold = execute(bought, "AAPL", -100, 60.0, fee=2.0)
    valuation = sold.value({})

    assert bought.cash == 94_998.0
    assert sold.cash == 100_996.0
    assert sold.fees_paid == 4.0
    assert sold.gross_realized_pnl == 1_000.0
    assert valuation.total_pnl == 996.0
    assert_reconciled(valuation)


def test_zero_cost_equal_price_round_trip_preserves_equity() -> None:
    bought = execute(starting(), "AAPL", 100, 50.0)
    closed = execute(bought, "AAPL", -100, 50.0)
    position = closed.get_position("AAPL")
    valuation = closed.value({})

    assert closed.cash == INITIAL_CASH
    assert position == PositionState("AAPL", 0, None, 0.0)
    assert closed.gross_realized_pnl == 0.0
    assert closed.fees_paid == 0.0
    assert valuation.equity == INITIAL_CASH
    assert valuation.total_pnl == 0.0
    assert_reconciled(valuation)


def test_fill_returns_new_deterministic_snapshot_without_mutating_original() -> None:
    original = starting()

    first = execute(original, "AAPL", 100, 50.0, fee=1.0)
    repeated = execute(original, "AAPL", 100, 50.0, fee=1.0)

    assert first is not original
    assert first == repeated
    assert original == starting()
    assert original.positions == ()


def test_fill_maintains_sorted_unique_position_order() -> None:
    state = execute(starting(), "MSFT", 5, 100.0)
    state = execute(state, "AAPL", 10, 50.0)
    state = execute(state, "NVDA", -2, 200.0)
    state = execute(state, "MSFT", 5, 120.0)

    assert tuple(position.symbol for position in state.positions) == ("AAPL", "MSFT", "NVDA")
    assert len({position.symbol for position in state.positions}) == 3


def test_cash_only_valuation_is_immutable_hashable_and_reconciled() -> None:
    valuation = starting().value({})

    assert tuple(field.name for field in fields(PortfolioValuation)) == (
        "initial_cash",
        "cash",
        "market_value",
        "equity",
        "gross_realized_pnl",
        "unrealized_pnl",
        "fees_paid",
        "total_pnl",
    )
    assert valuation == PortfolioValuation(
        INITIAL_CASH,
        INITIAL_CASH,
        0.0,
        INITIAL_CASH,
        0.0,
        0.0,
        0.0,
        0.0,
    )
    with pytest.raises(FrozenInstanceError):
        valuation.equity = 0.0  # type: ignore[misc]
    assert {valuation: "marked"}[valuation] == "marked"
    assert_reconciled(valuation)


def test_mixed_long_and_short_valuation_uses_signed_market_value_and_unrealized_pnl() -> None:
    state = execute(starting(), "AAPL", 100, 50.0)
    state = execute(state, "MSFT", -50, 80.0)
    valuation = state.value({"AAPL": 60.0, "MSFT": 70.0})

    assert state.cash == 99_000.0
    assert valuation.market_value == 2_500.0
    assert valuation.unrealized_pnl == 1_500.0
    assert valuation.equity == 101_500.0
    assert valuation.total_pnl == 1_500.0
    assert_reconciled(valuation)


def test_every_open_position_requires_an_exact_symbol_mark() -> None:
    state = execute(starting(), "AAPL", 100, 50.0)

    with pytest.raises(KeyError, match="missing mark for open position 'AAPL'"):
        state.value({})
    with pytest.raises(KeyError, match="missing mark for open position 'AAPL'"):
        state.value({"aapl": 50.0})


def test_flat_historical_position_requires_no_mark_and_extra_marks_are_ignored() -> None:
    state = execute(starting(), "AAPL", 100, 50.0)
    state = execute(state, "AAPL", -100, 60.0)

    without_marks = state.value({})
    with_unused_invalid_mark = state.value({"UNHELD": 0.0})

    assert without_marks == with_unused_invalid_mark
    assert without_marks.market_value == 0.0
    assert without_marks.gross_realized_pnl == 1_000.0


@pytest.mark.parametrize("mark", [0.0, -1.0, nan, inf, -inf])
def test_valuation_rejects_nonpositive_or_nonfinite_required_mark(mark: float) -> None:
    state = execute(starting(), "AAPL", 1, 50.0)

    with pytest.raises(ValueError, match="mark for AAPL"):
        state.value({"AAPL": mark})


@pytest.mark.parametrize("mark", [50, True])
def test_valuation_rejects_nonfloat_required_mark(mark: object) -> None:
    state = execute(starting(), "AAPL", 1, 50.0)

    with pytest.raises(TypeError, match="mark for AAPL must be a float"):
        state.value({"AAPL": mark})  # type: ignore[dict-item]


def test_valuation_requires_marks_mapping() -> None:
    with pytest.raises(TypeError, match="marks must be a mapping"):
        starting().value([])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("equity", 99_999.0),
        ("total_pnl", 1.0),
        ("gross_realized_pnl", 1.0),
    ],
)
def test_portfolio_valuation_rejects_broken_accounting_identity(
    field_name: str,
    replacement: float,
) -> None:
    values = {
        "initial_cash": INITIAL_CASH,
        "cash": INITIAL_CASH,
        "market_value": 0.0,
        "equity": INITIAL_CASH,
        "gross_realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "fees_paid": 0.0,
        "total_pnl": 0.0,
    }
    values[field_name] = replacement

    with pytest.raises(ValueError):
        PortfolioValuation(**values)


def test_portfolio_module_introduces_no_order_execution_or_strategy_objects() -> None:
    for excluded in (
        "Order",
        "OrderType",
        "Fill",
        "Signal",
        "Strategy",
        "ExecutionSimulator",
        "CommissionModel",
        "SlippageModel",
        "EventLoop",
    ):
        assert not hasattr(portfolio_module, excluded)
