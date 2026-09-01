"""Tests for the standard-library streaming CSV market-data provider."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from quantforge.data.csv import CSVMarketDataProvider
from quantforge.domain import Bar

REQUIRED_HEADERS = ("symbol", "timestamp", "open", "high", "low", "close", "volume")
HEADER = ",".join(REQUIRED_HEADERS)
TIMESTAMP = "2026-08-31T09:30:00-04:00"


def csv_row(
    *,
    symbol: str = "AAPL",
    timestamp: str = TIMESTAMP,
    open_price: str = "100.0",
    high: str = "105.0",
    low: str = "99.0",
    close: str = "103.0",
    volume: str = "1000000",
) -> str:
    return ",".join((symbol, timestamp, open_price, high, low, close, volume))


def write_csv(tmp_path: Path, contents: str) -> Path:
    path = tmp_path / "bars.csv"
    path.write_text(contents, encoding="utf-8")
    return path


@pytest.mark.parametrize("use_string_path", [False, True])
def test_provider_accepts_path_and_string_and_parses_one_row(
    tmp_path: Path, use_string_path: bool
) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row()}\n")
    provider_path: str | Path = str(path) if use_string_path else path

    bars = list(CSVMarketDataProvider(provider_path).iter_bars())

    assert bars == [
        Bar(
            symbol="AAPL",
            timestamp=datetime.fromisoformat(TIMESTAMP),
            open=100.0,
            high=105.0,
            low=99.0,
            close=103.0,
            volume=1_000_000,
        )
    ]


def test_provider_integrates_multiple_symbols_into_exact_bar_sequence(tmp_path: Path) -> None:
    second_timestamp = "2026-08-31T13:30:00+00:00"
    contents = "\n".join(
        (
            HEADER,
            csv_row(symbol="aapl"),
            csv_row(
                symbol="MSFT",
                timestamp=second_timestamp,
                open_price="200.0",
                high="206.0",
                low="198.0",
                close="204.0",
                volume="750000",
            ),
        )
    )

    assert list(CSVMarketDataProvider(write_csv(tmp_path, contents)).iter_bars()) == [
        Bar("AAPL", datetime.fromisoformat(TIMESTAMP), 100.0, 105.0, 99.0, 103.0, 1_000_000),
        Bar(
            "MSFT",
            datetime.fromisoformat(second_timestamp),
            200.0,
            206.0,
            198.0,
            204.0,
            750_000,
        ),
    ]


def test_provider_defers_file_access_until_iteration(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.csv"
    iterator = CSVMarketDataProvider(missing_path).iter_bars()

    with pytest.raises(FileNotFoundError):
        next(iterator)


def test_provider_propagates_directory_error(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        list(CSVMarketDataProvider(tmp_path).iter_bars())


def test_provider_streams_rows_and_does_not_parse_a_later_row_eagerly(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row()}\n{csv_row(open_price='invalid')}\n")
    iterator = CSVMarketDataProvider(path).iter_bars()

    assert iter(iterator) is iterator
    assert next(iterator).symbol == "AAPL"
    with pytest.raises(ValueError, match=r"CSV line 3: invalid open"):
        next(iterator)


def test_provider_preserves_duplicates_and_out_of_order_timestamps(tmp_path: Path) -> None:
    later = csv_row(timestamp="2026-09-02T09:30:00-04:00")
    earlier = csv_row(timestamp="2026-09-01T09:30:00-04:00")
    path = write_csv(tmp_path, f"{HEADER}\n{later}\n{earlier}\n{earlier}\n")

    bars = list(CSVMarketDataProvider(path).iter_bars())

    assert [bar.timestamp for bar in bars] == [
        datetime.fromisoformat("2026-09-02T09:30:00-04:00"),
        datetime.fromisoformat("2026-09-01T09:30:00-04:00"),
        datetime.fromisoformat("2026-09-01T09:30:00-04:00"),
    ]
    assert bars[1] == bars[2]
    assert len(bars) == 3


def test_provider_delegates_symbol_normalization_to_bar(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row(symbol=' aapl ')}\n")

    assert next(CSVMarketDataProvider(path).iter_bars()).symbol == "AAPL"


@pytest.mark.parametrize("missing_header", REQUIRED_HEADERS)
def test_provider_rejects_each_missing_required_header(tmp_path: Path, missing_header: str) -> None:
    headers = [header for header in REQUIRED_HEADERS if header != missing_header]
    path = write_csv(tmp_path, ",".join(headers) + "\n")

    with pytest.raises(ValueError, match=rf"missing required columns:.*{missing_header}"):
        list(CSVMarketDataProvider(path).iter_bars())


def test_provider_identifies_multiple_missing_headers(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "symbol,timestamp,volume\n")

    with pytest.raises(ValueError, match="open, high, low, close"):
        list(CSVMarketDataProvider(path).iter_bars())


def test_provider_trims_header_whitespace_and_ignores_extra_columns(tmp_path: Path) -> None:
    spaced_header = ",".join(f" {header} " for header in REQUIRED_HEADERS)
    path = write_csv(tmp_path, f"{spaced_header},provider\n{csv_row()},ignored\n")

    bar = next(CSVMarketDataProvider(path).iter_bars())

    assert bar.symbol == "AAPL"
    assert not hasattr(bar, "provider")


def test_provider_accepts_header_only_file(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n")

    assert list(CSVMarketDataProvider(path).iter_bars()) == []


def test_provider_rejects_completely_empty_file(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "")

    with pytest.raises(ValueError, match="CSV is missing required columns"):
        list(CSVMarketDataProvider(path).iter_bars())


def test_provider_accepts_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "bom.csv"
    path.write_bytes(f"\ufeff{HEADER}\n{csv_row()}\n".encode())

    assert next(CSVMarketDataProvider(path).iter_bars()).symbol == "AAPL"


def test_provider_rejects_naive_timestamp_through_bar_with_line_context(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row(timestamp='2026-08-31T09:30:00')}\n")

    with pytest.raises(
        ValueError, match=r"CSV line 2:.*timestamp must be timezone-aware"
    ) as exc_info:
        list(CSVMarketDataProvider(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "timestamp must be timezone-aware"


def test_provider_rejects_malformed_timestamp_with_cause_and_line_context(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row(timestamp='not-a-timestamp')}\n")

    with pytest.raises(ValueError, match=r"CSV line 2: invalid timestamp") as exc_info:
        list(CSVMarketDataProvider(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("field_name", ["open", "high", "low", "close"])
def test_provider_identifies_malformed_price_field(tmp_path: Path, field_name: str) -> None:
    values = {
        "symbol": "AAPL",
        "timestamp": TIMESTAMP,
        "open": "100.0",
        "high": "105.0",
        "low": "99.0",
        "close": "103.0",
        "volume": "1000000",
    }
    values[field_name] = "invalid"
    path = write_csv(tmp_path, f"{HEADER}\n{','.join(values[name] for name in REQUIRED_HEADERS)}\n")

    with pytest.raises(ValueError, match=rf"CSV line 2: invalid {field_name}") as exc_info:
        list(CSVMarketDataProvider(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("invalid_price", ["0", "-1", "NaN", "inf", "-inf"])
def test_provider_does_not_repair_invalid_price_domain_values(
    tmp_path: Path, invalid_price: str
) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row(open_price=invalid_price)}\n")

    with pytest.raises(ValueError, match=r"CSV line 2:.*open must be finite") as exc_info:
        list(CSVMarketDataProvider(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "open must be finite" in str(exc_info.value.__cause__)


def test_provider_allows_zero_volume(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row(volume='0')}\n")

    assert next(CSVMarketDataProvider(path).iter_bars()).volume == 0


def test_provider_rejects_negative_volume_through_bar(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row(volume='-1')}\n")

    with pytest.raises(ValueError, match=r"CSV line 2:.*volume must be a non-negative") as exc_info:
        list(CSVMarketDataProvider(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize("invalid_volume", ["100.5", ""])
def test_provider_rejects_non_integral_or_empty_volume(tmp_path: Path, invalid_volume: str) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row(volume=invalid_volume)}\n")

    with pytest.raises(ValueError, match=r"CSV line 2: invalid volume") as exc_info:
        list(CSVMarketDataProvider(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_provider_rejects_invalid_ohlc_through_bar(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n{csv_row(high='90.0')}\n")

    with pytest.raises(ValueError, match=r"CSV line 2:.*high must be greater") as exc_info:
        list(CSVMarketDataProvider(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_provider_rejects_short_row_with_line_context(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\nAAPL,{TIMESTAMP},100.0\n")

    with pytest.raises(ValueError, match=r"CSV line 2: missing value for high"):
        list(CSVMarketDataProvider(path).iter_bars())


def test_provider_does_not_silently_skip_blank_row(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f"{HEADER}\n\n")

    with pytest.raises(ValueError, match=r"CSV line 2: missing value for symbol"):
        list(CSVMarketDataProvider(path).iter_bars())


def test_provider_reports_malformed_csv_syntax_with_line_context(tmp_path: Path) -> None:
    path = write_csv(tmp_path, f'{HEADER}\nAAPL,"{TIMESTAMP},100.0,105.0,99.0,103.0,1000000\n')

    with pytest.raises(ValueError, match=r"CSV parsing failed near line 2") as exc_info:
        list(CSVMarketDataProvider(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, Exception)
