"""Streaming ingestion for the canonical QuantForge CSV schema."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Protocol

from quantforge.domain import Bar

__all__ = ["CSVMarketDataProvider"]

_REQUIRED_COLUMNS = ("symbol", "timestamp", "open", "high", "low", "close", "volume")


class _CSVReader(Protocol):
    line_num: int

    def __iter__(self) -> Iterator[list[str]]: ...

    def __next__(self) -> list[str]: ...


class CSVMarketDataProvider:
    """Read canonical OHLCV rows incrementally from a local CSV file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def iter_bars(self) -> Iterator[Bar]:
        """Yield validated bars in CSV row order."""
        with self._path.open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file, strict=True)
            column_indexes = _read_column_indexes(reader)

            try:
                for row in reader:
                    yield _parse_bar(row, column_indexes, reader.line_num)
            except csv.Error as exc:
                raise ValueError(f"CSV parsing failed near line {reader.line_num}: {exc}") from exc


def _read_column_indexes(reader: _CSVReader) -> dict[str, int]:
    try:
        header = next(reader)
    except StopIteration:
        _raise_missing_columns(_REQUIRED_COLUMNS)
    except csv.Error as exc:
        raise ValueError(f"CSV header parsing failed at line {reader.line_num}: {exc}") from exc

    normalized_header = [name.strip() for name in header]
    missing_columns = [name for name in _REQUIRED_COLUMNS if name not in normalized_header]
    if missing_columns:
        _raise_missing_columns(missing_columns)

    return {name: normalized_header.index(name) for name in _REQUIRED_COLUMNS}


def _raise_missing_columns(columns: tuple[str, ...] | list[str]) -> None:
    raise ValueError(f"CSV is missing required columns: {', '.join(columns)}")


def _parse_bar(row: list[str], column_indexes: dict[str, int], line_number: int) -> Bar:
    symbol = _row_value(row, column_indexes, "symbol", line_number)
    timestamp = _parse_timestamp(
        _row_value(row, column_indexes, "timestamp", line_number), line_number
    )
    open_price = _parse_price(row, column_indexes, "open", line_number)
    high = _parse_price(row, column_indexes, "high", line_number)
    low = _parse_price(row, column_indexes, "low", line_number)
    close = _parse_price(row, column_indexes, "close", line_number)
    volume = _parse_volume(_row_value(row, column_indexes, "volume", line_number), line_number)

    try:
        return Bar(
            symbol=symbol,
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
    except TypeError as exc:
        raise TypeError(f"CSV line {line_number}: invalid bar: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"CSV line {line_number}: invalid bar: {exc}") from exc


def _row_value(
    row: list[str], column_indexes: dict[str, int], field_name: str, line_number: int
) -> str:
    column_index = column_indexes[field_name]
    try:
        return row[column_index]
    except IndexError as exc:
        raise ValueError(f"CSV line {line_number}: missing value for {field_name}") from exc


def _parse_timestamp(value: str, line_number: int) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"CSV line {line_number}: invalid timestamp {value!r}") from exc


def _parse_price(
    row: list[str], column_indexes: dict[str, int], field_name: str, line_number: int
) -> float:
    value = _row_value(row, column_indexes, field_name, line_number)
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"CSV line {line_number}: invalid {field_name} value {value!r}") from exc


def _parse_volume(value: str, line_number: int) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"CSV line {line_number}: invalid volume value {value!r}") from exc
