"""Versioned JSON catalog for immutable local market-data records."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast
from uuid import uuid4

from quantforge.data.parquet import ParquetMarketDataStore

__all__ = ["DatasetCatalog", "DatasetIntegrityReport", "DatasetRecord"]

_CATALOG_VERSION = 1
_PARQUET_SCHEMA_VERSION = 1
_HASH_CHUNK_SIZE = 1024 * 1024
_DATASET_RECORD_KEYS = {
    "dataset_id",
    "format",
    "storage_path",
    "source",
    "file_sha256",
    "byte_size",
    "row_count",
    "symbols",
    "earliest_timestamp",
    "latest_timestamp",
    "parquet_schema_version",
    "registered_at",
}
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    """Immutable identity, provenance, summary, and integrity metadata."""

    dataset_id: str
    format: str
    storage_path: str
    source: str
    file_sha256: str
    byte_size: int
    row_count: int
    symbols: tuple[str, ...]
    earliest_timestamp: datetime | None
    latest_timestamp: datetime | None
    parquet_schema_version: int
    registered_at: datetime

    def __post_init__(self) -> None:
        """Reject records that violate the version-1 catalog contract."""
        if not isinstance(self.dataset_id, str) or not self.dataset_id:
            raise ValueError("dataset_id must be a non-empty string")
        if self.format != "parquet":
            raise ValueError("format must be 'parquet'")
        _validate_storage_path(self.storage_path)
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        if (
            not isinstance(self.file_sha256, str)
            or _SHA256_PATTERN.fullmatch(self.file_sha256) is None
        ):
            raise ValueError("file_sha256 must be 64 lowercase hexadecimal characters")
        _validate_non_negative_integer("byte_size", self.byte_size)
        _validate_non_negative_integer("row_count", self.row_count)
        _validate_symbols(self.symbols)
        if (
            isinstance(self.parquet_schema_version, bool)
            or not isinstance(self.parquet_schema_version, int)
            or self.parquet_schema_version != _PARQUET_SCHEMA_VERSION
        ):
            raise ValueError(f"parquet_schema_version must be {_PARQUET_SCHEMA_VERSION}")
        _validate_utc_datetime("registered_at", self.registered_at)
        _validate_summary_bounds(self)

    @property
    def unique_symbols(self) -> int:
        """Return the number of distinct symbols in the dataset summary."""
        return len(self.symbols)


@dataclass(frozen=True, slots=True)
class DatasetIntegrityReport:
    """Immutable comparison of a catalog record with its current artifact."""

    dataset_id: str
    path_exists: bool
    byte_size_matches: bool
    sha256_matches: bool

    @property
    def is_intact(self) -> bool:
        """Return whether the artifact exists and matches its recorded bytes."""
        return self.path_exists and self.byte_size_matches and self.sha256_matches


class DatasetCatalog:
    """Register and inspect immutable metadata for local Parquet datasets."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def register_parquet(self, path: str | Path, *, source: str) -> DatasetRecord:
        """Register one supported Parquet artifact without modifying it."""
        normalized_source = _normalize_source(source)
        records = self._load_records()
        artifact_path, storage_path = _normalize_artifact_path(path, self._path.parent)

        existing_record = next(
            (record for record in records if record.storage_path == storage_path),
            None,
        )
        if existing_record is not None:
            current_sha256, _ = _fingerprint(artifact_path)
            if current_sha256 == existing_record.file_sha256:
                return existing_record
            raise ValueError(f"registered dataset artifact has changed: {storage_path}")

        row_count, symbols, earliest_timestamp, latest_timestamp = _summarize_parquet(artifact_path)
        file_sha256, byte_size = _fingerprint(artifact_path)
        dataset_id = _generate_dataset_id({record.dataset_id for record in records})
        record = DatasetRecord(
            dataset_id=dataset_id,
            format="parquet",
            storage_path=storage_path,
            source=normalized_source,
            file_sha256=file_sha256,
            byte_size=byte_size,
            row_count=row_count,
            symbols=symbols,
            earliest_timestamp=earliest_timestamp,
            latest_timestamp=latest_timestamp,
            parquet_schema_version=_PARQUET_SCHEMA_VERSION,
            registered_at=_registration_time(),
        )
        _write_catalog(self._path, (*records, record))
        return record

    def get(self, dataset_id: str) -> DatasetRecord:
        """Return a registered record or raise ``KeyError`` when unknown."""
        for record in self._load_records():
            if record.dataset_id == dataset_id:
                return record
        raise KeyError(dataset_id)

    def list_records(self) -> tuple[DatasetRecord, ...]:
        """Return records in deterministic registration order."""
        return self._load_records()

    def verify(self, dataset_id: str) -> DatasetIntegrityReport:
        """Compare a registered fingerprint with the current artifact bytes."""
        record = self.get(dataset_id)
        artifact_path = _resolve_storage_path(record.storage_path, self._path.parent)
        try:
            file_sha256, byte_size = _fingerprint(artifact_path)
        except FileNotFoundError:
            return DatasetIntegrityReport(
                dataset_id=dataset_id,
                path_exists=False,
                byte_size_matches=False,
                sha256_matches=False,
            )
        return DatasetIntegrityReport(
            dataset_id=dataset_id,
            path_exists=True,
            byte_size_matches=byte_size == record.byte_size,
            sha256_matches=file_sha256 == record.file_sha256,
        )

    def _load_records(self) -> tuple[DatasetRecord, ...]:
        try:
            with self._path.open(mode="r", encoding="utf-8") as catalog_file:
                try:
                    raw_catalog: object = json.load(catalog_file)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"catalog contains invalid JSON: {self._path}") from exc
                except UnicodeDecodeError as exc:
                    raise ValueError(f"catalog is not valid UTF-8: {self._path}") from exc
        except FileNotFoundError:
            return ()

        catalog = _require_object(raw_catalog, "catalog")
        if set(catalog) != {"catalog_version", "datasets"}:
            raise ValueError("catalog must contain exactly catalog_version and datasets")
        catalog_version = _require_integer(catalog["catalog_version"], "catalog_version")
        if catalog_version != _CATALOG_VERSION:
            raise ValueError(
                f"unsupported catalog version: expected {_CATALOG_VERSION}, found {catalog_version}"
            )
        raw_datasets = catalog["datasets"]
        if not isinstance(raw_datasets, list):
            raise ValueError("catalog datasets must be a list")

        records: list[DatasetRecord] = []
        dataset_ids: set[str] = set()
        storage_paths: set[str] = set()
        for index, raw_record in enumerate(cast(list[object], raw_datasets), start=1):
            try:
                record = _record_from_json(raw_record)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid catalog dataset record {index}: {exc}") from exc
            if record.dataset_id in dataset_ids:
                raise ValueError(f"catalog contains duplicate dataset_id: {record.dataset_id}")
            if record.storage_path in storage_paths:
                raise ValueError(f"catalog contains duplicate storage_path: {record.storage_path}")
            dataset_ids.add(record.dataset_id)
            storage_paths.add(record.storage_path)
            records.append(record)
        return tuple(records)


def _normalize_source(source: object) -> str:
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    normalized = source.strip()
    if not normalized:
        raise ValueError("source must be a non-empty string")
    return normalized


def _normalize_artifact_path(path: str | Path, catalog_parent: Path) -> tuple[Path, str]:
    artifact_path = Path(path).resolve(strict=True)
    catalog_parent_path = catalog_parent.resolve()
    try:
        relative_path = os.path.relpath(artifact_path, start=catalog_parent_path)
    except ValueError as exc:
        raise ValueError("dataset artifact cannot be represented relative to the catalog") from exc
    return artifact_path, Path(relative_path).as_posix()


def _resolve_storage_path(storage_path: str, catalog_parent: Path) -> Path:
    portable_path = PurePosixPath(storage_path)
    return catalog_parent.joinpath(*portable_path.parts)


def _summarize_parquet(
    path: Path,
) -> tuple[int, tuple[str, ...], datetime | None, datetime | None]:
    row_count = 0
    symbols: set[str] = set()
    earliest_timestamp: datetime | None = None
    latest_timestamp: datetime | None = None
    for bar in ParquetMarketDataStore(path).iter_bars():
        row_count += 1
        symbols.add(bar.symbol)
        if earliest_timestamp is None or bar.timestamp < earliest_timestamp:
            earliest_timestamp = bar.timestamp
        if latest_timestamp is None or bar.timestamp > latest_timestamp:
            latest_timestamp = bar.timestamp
    return row_count, tuple(sorted(symbols)), earliest_timestamp, latest_timestamp


def _fingerprint(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_size = 0
    with path.open(mode="rb") as artifact_file:
        while chunk := artifact_file.read(_HASH_CHUNK_SIZE):
            digest.update(chunk)
            byte_size += len(chunk)
    return digest.hexdigest(), byte_size


def _generate_dataset_id(existing_ids: set[str]) -> str:
    while True:
        candidate = f"ds_{uuid4().hex}"
        if candidate not in existing_ids:
            return candidate


def _registration_time() -> datetime:
    return datetime.now(UTC)


def _write_catalog(path: Path, records: tuple[DatasetRecord, ...]) -> None:
    payload: dict[str, object] = {
        "catalog_version": _CATALOG_VERSION,
        "datasets": [_record_to_json(record) for record in records],
    }
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    published = False
    try:
        with temporary_path.open(mode="w", encoding="utf-8", newline="\n") as catalog_file:
            json.dump(payload, catalog_file, ensure_ascii=False, indent=2)
            catalog_file.write("\n")
            catalog_file.flush()
            os.fsync(catalog_file.fileno())
        os.replace(temporary_path, path)
        published = True
    finally:
        if not published:
            _remove_temporary_file(temporary_path)


def _remove_temporary_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _record_to_json(record: DatasetRecord) -> dict[str, object]:
    return {
        "dataset_id": record.dataset_id,
        "format": record.format,
        "storage_path": record.storage_path,
        "source": record.source,
        "file_sha256": record.file_sha256,
        "byte_size": record.byte_size,
        "row_count": record.row_count,
        "symbols": list(record.symbols),
        "earliest_timestamp": _serialize_timestamp(record.earliest_timestamp),
        "latest_timestamp": _serialize_timestamp(record.latest_timestamp),
        "parquet_schema_version": record.parquet_schema_version,
        "registered_at": _serialize_timestamp(record.registered_at),
    }


def _record_from_json(raw_record: object) -> DatasetRecord:
    record = _require_object(raw_record, "dataset record")
    if set(record) != _DATASET_RECORD_KEYS:
        raise ValueError("dataset record has missing or unexpected fields")
    raw_symbols = record["symbols"]
    if not isinstance(raw_symbols, list):
        raise ValueError("symbols must be a list")
    symbols = tuple(_require_string(symbol, "symbol") for symbol in cast(list[object], raw_symbols))
    return DatasetRecord(
        dataset_id=_require_string(record["dataset_id"], "dataset_id"),
        format=_require_string(record["format"], "format"),
        storage_path=_require_string(record["storage_path"], "storage_path"),
        source=_require_string(record["source"], "source"),
        file_sha256=_require_string(record["file_sha256"], "file_sha256"),
        byte_size=_require_integer(record["byte_size"], "byte_size"),
        row_count=_require_integer(record["row_count"], "row_count"),
        symbols=symbols,
        earliest_timestamp=_parse_optional_timestamp(
            record["earliest_timestamp"], "earliest_timestamp"
        ),
        latest_timestamp=_parse_optional_timestamp(record["latest_timestamp"], "latest_timestamp"),
        parquet_schema_version=_require_integer(
            record["parquet_schema_version"], "parquet_schema_version"
        ),
        registered_at=_parse_timestamp(record["registered_at"], "registered_at"),
    )


def _require_object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be a JSON object with string keys")
    return cast(dict[str, object], value)


def _require_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _require_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _parse_optional_timestamp(value: object, name: str) -> datetime | None:
    if value is None:
        return None
    return _parse_timestamp(value, name)


def _parse_timestamp(value: object, name: str) -> datetime:
    timestamp_text = _require_string(value, name)
    try:
        timestamp = datetime.fromisoformat(timestamp_text)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid ISO-8601 timestamp") from exc
    _validate_utc_datetime(name, timestamp)
    return timestamp.astimezone(UTC)


def _serialize_timestamp(timestamp: datetime | None) -> str | None:
    if timestamp is None:
        return None
    return timestamp.astimezone(UTC).isoformat()


def _validate_storage_path(storage_path: object) -> None:
    if not isinstance(storage_path, str) or not storage_path or "\\" in storage_path:
        raise ValueError("storage_path must be a non-empty POSIX-style relative path")
    portable_path = PurePosixPath(storage_path)
    windows_path = PureWindowsPath(storage_path)
    if portable_path.is_absolute() or windows_path.drive:
        raise ValueError("storage_path must be relative")
    if portable_path == PurePosixPath("."):
        raise ValueError("storage_path must identify an artifact")


def _validate_non_negative_integer(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_symbols(symbols: object) -> None:
    if not isinstance(symbols, tuple) or not all(
        isinstance(symbol, str) and symbol for symbol in symbols
    ):
        raise ValueError("symbols must be a tuple of non-empty strings")
    if tuple(sorted(set(symbols))) != symbols:
        raise ValueError("symbols must be sorted and unique")


def _validate_utc_datetime(name: str, value: object) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{name} must use UTC")


def _validate_summary_bounds(record: DatasetRecord) -> None:
    if record.row_count == 0:
        if record.symbols:
            raise ValueError("empty datasets must not contain symbols")
        if record.earliest_timestamp is not None or record.latest_timestamp is not None:
            raise ValueError("empty datasets must not contain timestamp bounds")
        return
    if not record.symbols:
        raise ValueError("non-empty datasets must contain symbols")
    if record.earliest_timestamp is None or record.latest_timestamp is None:
        raise ValueError("non-empty datasets must contain both timestamp bounds")
    _validate_utc_datetime("earliest_timestamp", record.earliest_timestamp)
    _validate_utc_datetime("latest_timestamp", record.latest_timestamp)
    if record.earliest_timestamp > record.latest_timestamp:
        raise ValueError("earliest_timestamp must not be after latest_timestamp")
