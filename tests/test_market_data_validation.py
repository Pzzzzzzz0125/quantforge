"""Tests for diagnostic market-data validation."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quantforge.data.csv import CSVMarketDataProvider
from quantforge.data.validation import (
    MarketDataValidator,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from quantforge.domain import Bar

BASE_TIMESTAMP = datetime(2026, 9, 1, 9, 30, tzinfo=UTC)


def make_bar(*, symbol: str = "AAPL", minute: int = 0, volume: int = 1_000) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=BASE_TIMESTAMP + timedelta(minutes=minute),
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=volume,
    )


def issue_codes(report: ValidationReport) -> list[str]:
    return [issue.code for issue in report.issues]


def test_validation_severity_has_stable_error_and_warning_values() -> None:
    assert ValidationSeverity.ERROR.value == "error"
    assert ValidationSeverity.WARNING.value == "warning"


def test_empty_iterable_returns_valid_warning_only_report() -> None:
    report = MarketDataValidator().validate([])

    assert report.total_bars == 0
    assert report.unique_symbols == 0
    assert report.earliest_timestamp is None
    assert report.latest_timestamp is None
    assert report.issues == (
        ValidationIssue(
            code="empty_dataset",
            severity=ValidationSeverity.WARNING,
            message="Dataset contains no bars",
        ),
    )
    assert report.is_valid
    assert report.errors == ()
    assert report.warnings == report.issues
    assert report.error_count == 0
    assert report.warning_count == 1


def test_one_bar_returns_complete_valid_summary() -> None:
    bar = make_bar()

    report = MarketDataValidator().validate([bar])

    assert report == ValidationReport(1, 1, bar.timestamp, bar.timestamp, ())
    assert report.is_valid


def test_list_tuple_and_generator_inputs_are_supported() -> None:
    bars = [make_bar(minute=0), make_bar(minute=1)]

    list_report = MarketDataValidator().validate(bars)
    tuple_report = MarketDataValidator().validate(tuple(bars))
    generator_report = MarketDataValidator().validate(bar for bar in bars)

    assert list_report == tuple_report == generator_report
    assert list_report.total_bars == 2


class _OnePassBars:
    def __init__(self, bars: list[Bar]) -> None:
        self._bars = bars
        self.iteration_count = 0

    def __iter__(self) -> Iterator[Bar]:
        self.iteration_count += 1
        if self.iteration_count > 1:
            raise AssertionError("input iterable was replayed")
        yield from self._bars


def test_validator_consumes_one_pass_iterable_exactly_once() -> None:
    bars = _OnePassBars([make_bar(minute=0), make_bar(minute=1)])

    report = MarketDataValidator().validate(bars)

    assert report.total_bars == 2
    assert bars.iteration_count == 1


def test_interleaved_symbols_are_checked_independently() -> None:
    bars = [
        make_bar(symbol="AAPL", minute=0),
        make_bar(symbol="MSFT", minute=10),
        make_bar(symbol="AAPL", minute=1),
        make_bar(symbol="MSFT", minute=11),
    ]

    report = MarketDataValidator().validate(bars)

    assert report.total_bars == 4
    assert report.unique_symbols == 2
    assert report.issues == ()
    assert report.is_valid


def test_timestamp_bounds_use_observed_extrema_regardless_of_input_order() -> None:
    bars = [make_bar(minute=10), make_bar(minute=20), make_bar(minute=0)]

    report = MarketDataValidator().validate(bars)

    assert report.earliest_timestamp == make_bar(minute=0).timestamp
    assert report.latest_timestamp == make_bar(minute=20).timestamp


def test_exact_duplicate_produces_structured_error_without_removing_bars() -> None:
    first = make_bar()
    duplicate = make_bar(volume=2_000)
    bars = [first, duplicate]

    report = MarketDataValidator().validate(bars)

    assert report.total_bars == 2
    assert report.issues == (
        ValidationIssue(
            code="duplicate_observation",
            severity=ValidationSeverity.ERROR,
            message=f"Duplicate observation for AAPL at {duplicate.timestamp.isoformat()}",
            symbol="AAPL",
            timestamp=duplicate.timestamp,
        ),
    )
    assert not report.is_valid
    assert report.error_count == 1
    assert report.warning_count == 0


def test_each_occurrence_after_first_duplicate_produces_an_issue() -> None:
    bar = make_bar()

    report = MarketDataValidator().validate([bar, bar, bar, bar])

    assert issue_codes(report) == ["duplicate_observation"] * 3
    assert report.total_bars == 4


def test_duplicate_separated_by_other_rows_is_detected() -> None:
    first = make_bar(symbol="AAPL", minute=0)

    report = MarketDataValidator().validate(
        [first, make_bar(symbol="MSFT", minute=0), make_bar(symbol="AAPL", minute=1), first]
    )

    assert "duplicate_observation" in issue_codes(report)


def test_equal_duplicate_timestamp_is_not_also_an_ordering_issue() -> None:
    bar = make_bar()

    report = MarketDataValidator().validate([bar, bar])

    assert issue_codes(report) == ["duplicate_observation"]


def test_adjacent_out_of_order_timestamp_produces_structured_error() -> None:
    current = make_bar(minute=1)

    report = MarketDataValidator().validate([make_bar(minute=2), current])

    assert report.issues == (
        ValidationIssue(
            code="out_of_order_timestamp",
            severity=ValidationSeverity.ERROR,
            message=(
                f"Timestamp {current.timestamp.isoformat()} for AAPL is earlier than previously "
                f"observed maximum {make_bar(minute=2).timestamp.isoformat()}"
            ),
            symbol="AAPL",
            timestamp=current.timestamp,
        ),
    )
    assert not report.is_valid


def test_out_of_order_timestamp_is_detected_across_interleaved_symbol() -> None:
    report = MarketDataValidator().validate(
        [
            make_bar(symbol="AAPL", minute=2),
            make_bar(symbol="MSFT", minute=0),
            make_bar(symbol="AAPL", minute=1),
        ]
    )

    assert issue_codes(report) == ["out_of_order_timestamp"]
    assert report.issues[0].symbol == "AAPL"


def test_cascading_out_of_order_timestamps_are_compared_with_observed_maximum() -> None:
    bars = [make_bar(minute=minute) for minute in (0, 5, 2, 4, 6)]

    report = MarketDataValidator().validate(bars)

    assert issue_codes(report) == ["out_of_order_timestamp", "out_of_order_timestamp"]
    assert [issue.timestamp for issue in report.issues] == [
        make_bar(minute=2).timestamp,
        make_bar(minute=4).timestamp,
    ]
    assert all(make_bar(minute=5).timestamp.isoformat() in issue.message for issue in report.issues)


def test_distinct_duplicate_and_ordering_problems_are_both_reported_in_order() -> None:
    repeated = make_bar(minute=2)

    report = MarketDataValidator().validate([repeated, make_bar(minute=3), repeated])

    assert issue_codes(report) == ["duplicate_observation", "out_of_order_timestamp"]
    assert all(issue.timestamp == repeated.timestamp for issue in report.issues)


def test_issue_order_is_deterministic_across_multiple_rows() -> None:
    repeated = make_bar(minute=2)
    bars = [
        repeated,
        make_bar(minute=1),
        make_bar(symbol="MSFT", minute=2),
        repeated,
        make_bar(symbol="MSFT", minute=1),
    ]

    first_report = MarketDataValidator().validate(bars)
    second_report = MarketDataValidator().validate(bars)

    assert issue_codes(first_report) == [
        "out_of_order_timestamp",
        "duplicate_observation",
        "out_of_order_timestamp",
    ]
    assert first_report == second_report


def test_validation_does_not_mutate_sort_or_deduplicate_input() -> None:
    first = make_bar(minute=2)
    bars = [first, make_bar(minute=1), first]
    original = tuple(bars)

    report = MarketDataValidator().validate(bars)

    assert tuple(bars) == original
    assert report.total_bars == len(bars)


def test_invalid_non_bar_item_raises_clear_type_error() -> None:
    bars: list[object] = [make_bar(), 42]

    with pytest.raises(TypeError, match=r"item 2 has type int"):
        MarketDataValidator().validate(bars)  # type: ignore[arg-type]


def test_issue_and_report_are_immutable() -> None:
    report = MarketDataValidator().validate([])

    with pytest.raises(FrozenInstanceError):
        setattr(report.issues[0], "code", "changed")
    with pytest.raises(FrozenInstanceError):
        setattr(report, "total_bars", 10)
    assert isinstance(report.issues, tuple)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"total_bars": -1}, "total_bars must be non-negative"),
        ({"unique_symbols": -1}, "unique_symbols must be non-negative"),
        ({"unique_symbols": 2}, "unique_symbols must not exceed total_bars"),
        ({"latest_timestamp": None}, "non-empty reports must contain both timestamp bounds"),
        (
            {"earliest_timestamp": BASE_TIMESTAMP + timedelta(minutes=1)},
            "earliest_timestamp must not be after latest_timestamp",
        ),
    ],
)
def test_report_rejects_invalid_summary_invariants(kwargs: dict[str, object], message: str) -> None:
    values: dict[str, object] = {
        "total_bars": 1,
        "unique_symbols": 1,
        "earliest_timestamp": BASE_TIMESTAMP,
        "latest_timestamp": BASE_TIMESTAMP,
        "issues": (),
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=message):
        ValidationReport(**values)  # type: ignore[arg-type]


def test_csv_provider_iterator_integrates_directly_with_validator(tmp_path: Path) -> None:
    csv_path = tmp_path / "bars.csv"
    csv_path.write_text(
        "\n".join(
            (
                "symbol,timestamp,open,high,low,close,volume",
                "AAPL,2026-09-01T09:32:00+00:00,100.0,105.0,95.0,102.0,1000",
                "MSFT,2026-09-01T09:30:00+00:00,100.0,105.0,95.0,102.0,1000",
                "AAPL,2026-09-01T09:31:00+00:00,100.0,105.0,95.0,102.0,1000",
                "AAPL,2026-09-01T09:31:00+00:00,100.0,105.0,95.0,102.0,1000",
            )
        ),
        encoding="utf-8",
    )

    report = MarketDataValidator().validate(CSVMarketDataProvider(csv_path).iter_bars())

    assert report.total_bars == 4
    assert report.unique_symbols == 2
    assert issue_codes(report) == [
        "out_of_order_timestamp",
        "duplicate_observation",
        "out_of_order_timestamp",
    ]
    assert not report.is_valid
