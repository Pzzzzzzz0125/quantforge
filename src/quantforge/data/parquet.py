"""Versioned, batch-oriented Parquet persistence for canonical market bars."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from quantforge.domain import Bar

__all__ = ["ParquetMarketDataStore"]

_SCHEMA_VERSION_KEY = b"quantforge_schema_version"
_SCHEMA_VERSION = b"1"
_WRITE_BATCH_SIZE = 1_024
_READ_BATCH_SIZE = 1_024
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


class _ArrowSchema(Protocol):
    names: list[str]
    metadata: dict[bytes, bytes] | None

    def equals(self, other: object, check_metadata: bool = False) -> bool: ...

    def remove_metadata(self) -> _ArrowSchema: ...


class _ArrowScalar(Protocol):
    def as_py(self) -> object: ...


class _ArrowArray(Protocol):
    def __getitem__(self, index: int) -> _ArrowScalar: ...


class _RecordBatch(Protocol):
    num_rows: int

    def column(self, index: int) -> _ArrowArray: ...


class _ParquetFile(Protocol):
    schema_arrow: _ArrowSchema

    def close(self, force: bool = False) -> None: ...

    def iter_batches(self, *, batch_size: int) -> Iterator[_RecordBatch]: ...


class _ParquetWriter(Protocol):
    def __enter__(self) -> _ParquetWriter: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> bool | None: ...

    def write_batch(self, batch: _RecordBatch) -> None: ...


_CANONICAL_MARKET_BAR_SCHEMA: _ArrowSchema = pa.schema(
    [
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("timestamp", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("volume", pa.int64(), nullable=False),
    ],
    metadata={_SCHEMA_VERSION_KEY: _SCHEMA_VERSION},
)


class ParquetMarketDataStore:
    """Persist canonical bars in one local, versioned Parquet file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def write_bars(self, bars: Iterable[Bar], *, overwrite: bool = False) -> int:
        """Write bars in encounter order and atomically publish the completed file."""
        if not overwrite and os.path.lexists(self._path):
            _raise_destination_exists(self._path)

        temporary_path = _create_temporary_path(self._path)
        published = False
        try:
            count = _write_temporary_file(temporary_path, bars)
            if not overwrite and os.path.lexists(self._path):
                _raise_destination_exists(self._path)
            os.replace(temporary_path, self._path)
            published = True
            return count
        finally:
            if not published:
                _remove_temporary_file(temporary_path)

    def iter_bars(self) -> Iterator[Bar]:
        """Yield canonical bars incrementally after validating file compatibility."""
        parquet_file = _open_parquet_file(self._path)
        try:
            _validate_schema(parquet_file.schema_arrow)
            position = 0
            try:
                for batch in parquet_file.iter_batches(batch_size=_READ_BATCH_SIZE):
                    for row_index in range(batch.num_rows):
                        position += 1
                        yield _bar_from_batch(batch, row_index, position)
            except pa.ArrowInvalid as exc:
                raise ValueError(f"Parquet read failed for {self._path}: {exc}") from exc
        finally:
            parquet_file.close()


def _create_temporary_path(destination: Path) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    return Path(temporary_name)


def _remove_temporary_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _raise_destination_exists(path: Path) -> None:
    raise FileExistsError(f"destination already exists: {path}; pass overwrite=True to replace it")


def _write_temporary_file(path: Path, bars: Iterable[Bar]) -> int:
    writer: _ParquetWriter = pq.ParquetWriter(
        path,
        _CANONICAL_MARKET_BAR_SCHEMA,
        compression="zstd",
    )
    count = 0
    pending: list[Bar] = []

    with writer:
        for position, bar in enumerate(bars, start=1):
            _validate_bar_for_storage(bar, position)
            pending.append(bar)
            if len(pending) == _WRITE_BATCH_SIZE:
                writer.write_batch(_record_batch(pending))
                count += len(pending)
                pending.clear()

        if pending:
            writer.write_batch(_record_batch(pending))
            count += len(pending)

    return count


def _validate_bar_for_storage(bar: object, position: int) -> None:
    if not isinstance(bar, Bar):
        raise TypeError(
            f"bars must contain only Bar instances; item {position} has type {type(bar).__name__}"
        )
    if not _INT64_MIN <= bar.volume <= _INT64_MAX:
        raise OverflowError(
            f"bar at position {position} has volume {bar.volume}, which is outside int64 range"
        )


def _record_batch(bars: Sequence[Bar]) -> _RecordBatch:
    arrays = [
        pa.array((bar.symbol for bar in bars), type=pa.string()),
        pa.array(
            (bar.timestamp.astimezone(UTC) for bar in bars),
            type=pa.timestamp("us", tz="UTC"),
        ),
        pa.array((bar.open for bar in bars), type=pa.float64()),
        pa.array((bar.high for bar in bars), type=pa.float64()),
        pa.array((bar.low for bar in bars), type=pa.float64()),
        pa.array((bar.close for bar in bars), type=pa.float64()),
        pa.array((bar.volume for bar in bars), type=pa.int64()),
    ]
    record_batch: _RecordBatch = pa.RecordBatch.from_arrays(
        arrays,
        schema=_CANONICAL_MARKET_BAR_SCHEMA,
    )
    return record_batch


def _open_parquet_file(path: Path) -> _ParquetFile:
    try:
        parquet_file: _ParquetFile = pq.ParquetFile(path)
    except pa.ArrowInvalid as exc:
        raise ValueError(f"Parquet file is corrupt or unreadable: {path}: {exc}") from exc
    return parquet_file


def _validate_schema(schema: _ArrowSchema) -> None:
    metadata = schema.metadata or {}
    version = metadata.get(_SCHEMA_VERSION_KEY)
    if version is None:
        raise ValueError("Parquet schema is missing quantforge_schema_version metadata")
    if version != _SCHEMA_VERSION:
        raise ValueError(
            "unsupported QuantForge Parquet schema version: "
            f"expected {_SCHEMA_VERSION.decode()}, found {version!r}"
        )

    expected = _CANONICAL_MARKET_BAR_SCHEMA.remove_metadata()
    actual = schema.remove_metadata()
    if not actual.equals(expected, check_metadata=False):
        raise ValueError(
            "incompatible QuantForge market-bar Parquet schema: "
            f"expected {expected}, found {actual}"
        )


def _bar_from_batch(batch: _RecordBatch, row_index: int, position: int) -> Bar:
    try:
        return Bar(
            symbol=cast(str, batch.column(0)[row_index].as_py()),
            timestamp=cast(datetime, batch.column(1)[row_index].as_py()),
            open=cast(float, batch.column(2)[row_index].as_py()),
            high=cast(float, batch.column(3)[row_index].as_py()),
            low=cast(float, batch.column(4)[row_index].as_py()),
            close=cast(float, batch.column(5)[row_index].as_py()),
            volume=cast(int, batch.column(6)[row_index].as_py()),
        )
    except TypeError as exc:
        raise TypeError(f"Parquet row {position}: invalid bar: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"Parquet row {position}: invalid bar: {exc}") from exc
