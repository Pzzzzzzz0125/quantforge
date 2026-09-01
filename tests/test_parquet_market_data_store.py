"""Tests for versioned, atomic Parquet persistence of canonical market bars."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

import quantforge.data.parquet as parquet_module
from quantforge.data.csv import CSVMarketDataProvider
from quantforge.data.parquet import ParquetMarketDataStore
from quantforge.data.validation import MarketDataValidator
from quantforge.domain import Bar

BASE_TIMESTAMP = datetime(2026, 9, 1, 9, 30, tzinfo=UTC)
SCHEMA_VERSION_KEY = b"quantforge_schema_version"
SCHEMA_VERSION = b"1"
FIELD_NAMES = ("symbol", "timestamp", "open", "high", "low", "close", "volume")


def make_bar(
    *,
    symbol: str = "AAPL",
    minute: int = 0,
    timestamp: datetime | None = None,
    open_price: float = 100.0,
    high: float = 105.0,
    low: float = 95.0,
    close: float = 102.0,
    volume: int = 1_000,
) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=timestamp or BASE_TIMESTAMP + timedelta(minutes=minute),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def canonical_arrow_schema(
    *,
    timestamp_type: Any | None = None,
    open_type: Any | None = None,
    metadata: dict[bytes, bytes] | None = None,
) -> Any:
    return pa.schema(
        [
            pa.field("symbol", pa.string(), nullable=False),
            pa.field(
                "timestamp",
                timestamp_type or pa.timestamp("us", tz="UTC"),
                nullable=False,
            ),
            pa.field("open", open_type or pa.float64(), nullable=False),
            pa.field("high", pa.float64(), nullable=False),
            pa.field("low", pa.float64(), nullable=False),
            pa.field("close", pa.float64(), nullable=False),
            pa.field("volume", pa.int64(), nullable=False),
        ],
        metadata={SCHEMA_VERSION_KEY: SCHEMA_VERSION} if metadata is None else metadata,
    )


def write_raw_table(
    path: Path,
    *,
    schema: Any | None = None,
    open_price: float = 100.0,
) -> None:
    selected_schema = schema or canonical_arrow_schema()
    table = pa.Table.from_pydict(
        {
            "symbol": ["AAPL"],
            "timestamp": [BASE_TIMESTAMP],
            "open": [open_price],
            "high": [105.0],
            "low": [95.0],
            "close": [102.0],
            "volume": [1_000],
        },
        schema=selected_schema,
    )
    pq.write_table(table, path)


def test_constructor_accepts_path_and_string_without_filesystem_access(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing"

    path_store = ParquetMarketDataStore(missing_parent / "path.parquet")
    string_store = ParquetMarketDataStore(str(missing_parent / "string.parquet"))

    assert isinstance(path_store, ParquetMarketDataStore)
    assert isinstance(string_store, ParquetMarketDataStore)
    assert not missing_parent.exists()


def test_one_bar_round_trip_preserves_domain_values(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    bar = make_bar(open_price=101.25, high=106.5, low=99.75, close=104.125, volume=0)
    store = ParquetMarketDataStore(path)

    assert store.write_bars([bar]) == 1
    result = list(store.iter_bars())

    assert result == [bar]
    assert isinstance(result[0], Bar)
    assert (result[0].open, result[0].high, result[0].low, result[0].close) == (
        101.25,
        106.5,
        99.75,
        104.125,
    )
    assert result[0].volume == 0


def test_schema_fields_types_metadata_and_compression_are_canonical(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    ParquetMarketDataStore(path).write_bars([make_bar()])

    parquet_file = pq.ParquetFile(path)
    schema = parquet_file.schema_arrow

    assert tuple(schema.names) == FIELD_NAMES
    assert schema.field("symbol").type == pa.string()
    assert schema.field("timestamp").type == pa.timestamp("us", tz="UTC")
    for field_name in ("open", "high", "low", "close"):
        assert schema.field(field_name).type == pa.float64()
    assert schema.field("volume").type == pa.int64()
    assert all(not field.nullable for field in schema)
    assert schema.metadata == {SCHEMA_VERSION_KEY: SCHEMA_VERSION}
    assert parquet_file.metadata.row_group(0).column(0).compression == "ZSTD"


def test_offset_timestamp_is_normalized_to_same_utc_instant(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    eastern = timezone(timedelta(hours=-4))
    source_timestamp = datetime(2026, 9, 1, 9, 30, tzinfo=eastern)
    store = ParquetMarketDataStore(path)

    store.write_bars([make_bar(timestamp=source_timestamp)])
    stored_timestamp = next(store.iter_bars()).timestamp

    assert stored_timestamp == source_timestamp
    assert stored_timestamp == datetime(2026, 9, 1, 13, 30, tzinfo=UTC)
    assert stored_timestamp.utcoffset() == timedelta(0)
    assert stored_timestamp.tzname() == "UTC"


def test_list_tuple_and_one_shot_generator_inputs_are_supported(tmp_path: Path) -> None:
    bars = [make_bar(minute=0), make_bar(minute=1)]
    stores = [
        ParquetMarketDataStore(tmp_path / "list.parquet"),
        ParquetMarketDataStore(tmp_path / "tuple.parquet"),
        ParquetMarketDataStore(tmp_path / "generator.parquet"),
    ]

    counts = [
        stores[0].write_bars(bars),
        stores[1].write_bars(tuple(bars)),
        stores[2].write_bars(bar for bar in bars),
    ]

    assert counts == [2, 2, 2]
    assert [list(store.iter_bars()) for store in stores] == [bars, bars, bars]


class _OnePassBars:
    def __init__(self, bars: list[Bar]) -> None:
        self._bars = bars
        self.iteration_count = 0

    def __iter__(self) -> Iterator[Bar]:
        self.iteration_count += 1
        if self.iteration_count > 1:
            raise AssertionError("input iterable was replayed")
        yield from self._bars


def test_writer_consumes_iterable_once_and_preserves_multiple_symbols(tmp_path: Path) -> None:
    bars = _OnePassBars(
        [
            make_bar(symbol="MSFT", minute=2),
            make_bar(symbol="AAPL", minute=0),
            make_bar(symbol="MSFT", minute=1),
        ]
    )
    store = ParquetMarketDataStore(tmp_path / "bars.parquet")

    assert store.write_bars(bars) == 3

    assert bars.iteration_count == 1
    assert [bar.symbol for bar in store.iter_bars()] == ["MSFT", "AAPL", "MSFT"]
    assert [bar.timestamp for bar in store.iter_bars()] == [
        make_bar(minute=2).timestamp,
        make_bar(minute=0).timestamp,
        make_bar(minute=1).timestamp,
    ]


def test_writer_uses_bounded_batches_without_changing_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(parquet_module, "_WRITE_BATCH_SIZE", 2)
    bars = [make_bar(minute=minute) for minute in range(5)]
    path = tmp_path / "bars.parquet"
    store = ParquetMarketDataStore(path)

    assert store.write_bars(bar for bar in bars) == 5

    assert pq.ParquetFile(path).metadata.num_row_groups == 3
    assert list(store.iter_bars()) == bars


def test_empty_iterable_creates_valid_zero_row_canonical_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.parquet"
    store = ParquetMarketDataStore(path)

    assert store.write_bars([]) == 0

    parquet_file = pq.ParquetFile(path)
    assert parquet_file.metadata.num_rows == 0
    assert tuple(parquet_file.schema_arrow.names) == FIELD_NAMES
    assert parquet_file.schema_arrow.metadata == {SCHEMA_VERSION_KEY: SCHEMA_VERSION}
    assert list(store.iter_bars()) == []


def test_signed_int64_maximum_volume_round_trips(tmp_path: Path) -> None:
    store = ParquetMarketDataStore(tmp_path / "bars.parquet")
    bar = make_bar(volume=2**63 - 1)

    assert store.write_bars([bar]) == 1
    assert next(store.iter_bars()).volume == 2**63 - 1


def test_volume_above_int64_range_fails_without_creating_destination(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    store = ParquetMarketDataStore(path)

    with pytest.raises(OverflowError, match=r"position 1.*outside int64 range"):
        store.write_bars([make_bar(volume=2**63)])

    assert not path.exists()


def test_non_bar_item_fails_with_position_and_no_destination(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    bars: list[object] = [make_bar(), 42]

    with pytest.raises(TypeError, match=r"item 2 has type int"):
        ParquetMarketDataStore(path).write_bars(bars)  # type: ignore[arg-type]

    assert not path.exists()


def test_missing_parent_directory_fails_without_creating_directories(tmp_path: Path) -> None:
    parent = tmp_path / "missing"
    store = ParquetMarketDataStore(parent / "bars.parquet")

    with pytest.raises(FileNotFoundError):
        store.write_bars([make_bar()])

    assert not parent.exists()


def test_existing_destination_is_protected_by_default(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    store = ParquetMarketDataStore(path)
    original = make_bar(symbol="AAPL")
    store.write_bars([original])
    original_bytes = path.read_bytes()

    with pytest.raises(FileExistsError, match=r"overwrite=True"):
        store.write_bars([make_bar(symbol="MSFT")])

    assert path.read_bytes() == original_bytes
    assert list(store.iter_bars()) == [original]


def test_explicit_overwrite_atomically_replaces_completed_destination(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    store = ParquetMarketDataStore(path)
    replacement = make_bar(symbol="MSFT", minute=1)
    store.write_bars([make_bar(symbol="AAPL")])

    assert store.write_bars([replacement], overwrite=True) == 1

    assert list(store.iter_bars()) == [replacement]


@pytest.mark.parametrize("existing_destination", [False, True])
def test_failed_write_is_atomic_and_cleans_partial_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing_destination: bool,
) -> None:
    monkeypatch.setattr(parquet_module, "_WRITE_BATCH_SIZE", 1)
    path = tmp_path / "bars.parquet"
    store = ParquetMarketDataStore(path)
    original = make_bar(symbol="ORIGINAL")
    original_bytes: bytes | None = None
    if existing_destination:
        store.write_bars([original])
        original_bytes = path.read_bytes()

    def failing_input() -> Iterator[object]:
        yield make_bar(symbol="NEW")
        yield "not-a-bar"

    with pytest.raises(TypeError, match=r"item 2 has type str"):
        store.write_bars(failing_input(), overwrite=True)  # type: ignore[arg-type]

    if existing_destination:
        assert original_bytes is not None
        assert path.read_bytes() == original_bytes
        assert list(store.iter_bars()) == [original]
    else:
        assert not path.exists()
    assert list(tmp_path.glob(".bars.parquet.*.tmp")) == []


def test_read_access_is_lazy_and_missing_path_error_is_meaningful(tmp_path: Path) -> None:
    iterator = ParquetMarketDataStore(tmp_path / "missing.parquet").iter_bars()

    assert iter(iterator) is iterator
    with pytest.raises(FileNotFoundError):
        next(iterator)


def test_reader_yields_incrementally_in_persisted_order(tmp_path: Path) -> None:
    bars = [make_bar(minute=minute) for minute in range(3)]
    store = ParquetMarketDataStore(tmp_path / "bars.parquet")
    store.write_bars(bars)

    iterator = store.iter_bars()

    assert next(iterator) == bars[0]
    assert list(iterator) == bars[1:]


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        ({}, "missing quantforge_schema_version"),
        ({SCHEMA_VERSION_KEY: b"999"}, "unsupported QuantForge Parquet schema version"),
    ],
)
def test_reader_rejects_missing_or_unsupported_schema_version_before_yield(
    tmp_path: Path, metadata: dict[bytes, bytes], message: str
) -> None:
    path = tmp_path / "bars.parquet"
    write_raw_table(path, schema=canonical_arrow_schema(metadata=metadata))

    with pytest.raises(ValueError, match=message):
        next(ParquetMarketDataStore(path).iter_bars())


@pytest.mark.parametrize(
    "schema",
    [
        canonical_arrow_schema(timestamp_type=pa.timestamp("us")),
        canonical_arrow_schema(open_type=pa.float32()),
    ],
    ids=["naive-timestamp", "incompatible-column"],
)
def test_reader_rejects_incompatible_schema_before_yield(tmp_path: Path, schema: Any) -> None:
    path = tmp_path / "bars.parquet"
    write_raw_table(path, schema=schema)

    with pytest.raises(ValueError, match="incompatible QuantForge market-bar Parquet schema"):
        next(ParquetMarketDataStore(path).iter_bars())


def test_corrupt_parquet_failure_preserves_pyarrow_cause(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.parquet"
    path.write_bytes(b"not a parquet file")

    with pytest.raises(ValueError, match="corrupt or unreadable") as exc_info:
        next(ParquetMarketDataStore(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, pa.ArrowInvalid)


def test_reader_reconstructs_through_bar_and_rejects_invalid_domain_values(tmp_path: Path) -> None:
    path = tmp_path / "invalid-domain.parquet"
    write_raw_table(path, open_price=-1.0)

    with pytest.raises(ValueError, match=r"Parquet row 1:.*open must be finite") as exc_info:
        next(ParquetMarketDataStore(path).iter_bars())

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_csv_provider_streams_directly_through_parquet_round_trip(tmp_path: Path) -> None:
    csv_path = tmp_path / "bars.csv"
    csv_path.write_text(
        "\n".join(
            (
                "symbol,timestamp,open,high,low,close,volume",
                "AAPL,2026-09-01T09:30:00-04:00,100.0,105.0,95.0,102.0,1000",
                "MSFT,2026-09-01T13:31:00+00:00,200.0,205.0,195.0,202.0,2000",
            )
        ),
        encoding="utf-8",
    )
    store = ParquetMarketDataStore(tmp_path / "bars.parquet")

    count = store.write_bars(CSVMarketDataProvider(csv_path).iter_bars())
    bars = list(store.iter_bars())

    assert count == 2
    assert [bar.symbol for bar in bars] == ["AAPL", "MSFT"]
    assert [bar.timestamp for bar in bars] == [
        datetime(2026, 9, 1, 13, 30, tzinfo=UTC),
        datetime(2026, 9, 1, 13, 31, tzinfo=UTC),
    ]


def test_duplicate_and_out_of_order_rows_survive_for_validator_diagnostics(tmp_path: Path) -> None:
    repeated = make_bar(minute=1)
    bars = [make_bar(minute=2), repeated, repeated]
    store = ParquetMarketDataStore(tmp_path / "bars.parquet")

    assert store.write_bars(bars) == 3
    persisted = list(store.iter_bars())
    report = MarketDataValidator().validate(store.iter_bars())

    assert persisted == bars
    assert [issue.code for issue in report.issues] == [
        "out_of_order_timestamp",
        "duplicate_observation",
        "out_of_order_timestamp",
    ]
