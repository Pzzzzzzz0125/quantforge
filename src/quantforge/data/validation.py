"""Diagnostic validation for iterables of canonical market bars."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from quantforge.domain import Bar

__all__ = [
    "MarketDataValidator",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
]


class ValidationSeverity(Enum):
    """Stable severity levels for market-data validation findings."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One immutable, structured market-data quality finding."""

    code: str
    severity: ValidationSeverity
    message: str
    symbol: str | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Immutable summary and findings from one validation pass."""

    total_bars: int
    unique_symbols: int
    earliest_timestamp: datetime | None
    latest_timestamp: datetime | None
    issues: tuple[ValidationIssue, ...]

    def __post_init__(self) -> None:
        """Reject internally inconsistent report summaries."""
        if self.total_bars < 0:
            raise ValueError("total_bars must be non-negative")
        if self.unique_symbols < 0:
            raise ValueError("unique_symbols must be non-negative")
        if self.unique_symbols > self.total_bars:
            raise ValueError("unique_symbols must not exceed total_bars")
        if self.total_bars == 0:
            if self.earliest_timestamp is not None or self.latest_timestamp is not None:
                raise ValueError("empty reports must not contain timestamp bounds")
        elif self.earliest_timestamp is None or self.latest_timestamp is None:
            raise ValueError("non-empty reports must contain both timestamp bounds")
        if (
            self.earliest_timestamp is not None
            and self.latest_timestamp is not None
            and self.earliest_timestamp > self.latest_timestamp
        ):
            raise ValueError("earliest_timestamp must not be after latest_timestamp")

    @property
    def is_valid(self) -> bool:
        """Return whether the report contains no error-severity findings."""
        return not any(issue.severity is ValidationSeverity.ERROR for issue in self.issues)

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        """Return error-severity findings in discovery order."""
        return tuple(issue for issue in self.issues if issue.severity is ValidationSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        """Return warning-severity findings in discovery order."""
        return tuple(issue for issue in self.issues if issue.severity is ValidationSeverity.WARNING)

    @property
    def error_count(self) -> int:
        """Return the number of error-severity findings."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Return the number of warning-severity findings."""
        return len(self.warnings)


class MarketDataValidator:
    """Validate dataset-level relationships without changing input bars."""

    def validate(self, bars: Iterable[Bar]) -> ValidationReport:
        """Consume bars once and return deterministic diagnostic findings."""
        seen: set[tuple[str, datetime]] = set()
        maximum_timestamp_by_symbol: dict[str, datetime] = {}
        symbols: set[str] = set()
        issues: list[ValidationIssue] = []
        total_bars = 0
        earliest_timestamp: datetime | None = None
        latest_timestamp: datetime | None = None

        for position, bar in enumerate(bars, start=1):
            if not isinstance(bar, Bar):
                raise TypeError(
                    "bars must contain only Bar instances; "
                    f"item {position} has type {type(bar).__name__}"
                )

            total_bars += 1
            symbols.add(bar.symbol)
            if earliest_timestamp is None or bar.timestamp < earliest_timestamp:
                earliest_timestamp = bar.timestamp
            if latest_timestamp is None or bar.timestamp > latest_timestamp:
                latest_timestamp = bar.timestamp

            observation_key = (bar.symbol, bar.timestamp)
            if observation_key in seen:
                issues.append(
                    ValidationIssue(
                        code="duplicate_observation",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Duplicate observation for {bar.symbol} at {bar.timestamp.isoformat()}"
                        ),
                        symbol=bar.symbol,
                        timestamp=bar.timestamp,
                    )
                )
            else:
                seen.add(observation_key)

            maximum_timestamp = maximum_timestamp_by_symbol.get(bar.symbol)
            if maximum_timestamp is not None and bar.timestamp < maximum_timestamp:
                issues.append(
                    ValidationIssue(
                        code="out_of_order_timestamp",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"Timestamp {bar.timestamp.isoformat()} for {bar.symbol} is earlier "
                            f"than previously observed maximum {maximum_timestamp.isoformat()}"
                        ),
                        symbol=bar.symbol,
                        timestamp=bar.timestamp,
                    )
                )
            if maximum_timestamp is None or bar.timestamp > maximum_timestamp:
                maximum_timestamp_by_symbol[bar.symbol] = bar.timestamp

        if total_bars == 0:
            issues.append(
                ValidationIssue(
                    code="empty_dataset",
                    severity=ValidationSeverity.WARNING,
                    message="Dataset contains no bars",
                )
            )

        return ValidationReport(
            total_bars=total_bars,
            unique_symbols=len(symbols),
            earliest_timestamp=earliest_timestamp,
            latest_timestamp=latest_timestamp,
            issues=tuple(issues),
        )
