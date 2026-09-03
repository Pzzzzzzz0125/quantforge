"""Tests for the versioned local dataset catalog."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from itertools import count
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest

import quantforge.data.catalog as catalog_module
from quantforge.data.catalog import DatasetCatalog, DatasetIntegrityReport, DatasetRecord
from quantforge.data.csv import CSVMarketDataProvider
from quantforge.data.parquet import ParquetMarketDataStore
from quantforge.data.validation import MarketDataValidator
from quantforge.domain import Bar

BASE_TIMESTAMP = datetime(2026, 9, 1, 9, 30, tzinfo=UTC)
REGISTERED_AT = datetime(2026, 9, 3, 18, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def deterministic_identity_and_registration_time(monkeypatch: pytest.MonkeyPatch) -> None:
    identifiers = count(1)
    monkeypatch.setattr(catalog_module, "uuid4", lambda: UUID(int=next(identifiers)))
    monkeypatch.setattr(catalog_module, "_registration_time", lambda: REGISTERED_AT)


def make_bar(*, symbol: str = "AAPL", minute: int = 0) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=BASE_TIMESTAMP + timedelta(minutes=minute),
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=1_000,
    )


def write_dataset(path: Path, bars: list[Bar]) -> ParquetMarketDataStore:
    store = ParquetMarketDataStore(path)
    store.write_bars(bars)
    return store


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_construction_is_lazy_and_missing_catalog_is_empty(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing"
    catalog = DatasetCatalog(missing_parent / "catalog.json")

    assert not missing_parent.exists()
    assert catalog.list_records() == ()
    assert not missing_parent.exists()


def test_registration_records_identity_provenance_summary_and_portable_json(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "data" / "catalog.json"
    artifact_path = tmp_path / "data" / "processed" / "bars.parquet"
    artifact_path.parent.mkdir(parents=True)
    bars = [
        make_bar(symbol="MSFT", minute=5),
        make_bar(symbol="AAPL", minute=0),
        make_bar(symbol="MSFT", minute=2),
    ]
    write_dataset(artifact_path, bars)
    artifact_before = artifact_path.read_bytes()
    expected_sha256 = hashlib.sha256(artifact_before).hexdigest()
    catalog = DatasetCatalog(catalog_path)

    record = catalog.register_parquet(artifact_path, source="  csv:data/raw/bars.csv  ")

    assert record == DatasetRecord(
        dataset_id="ds_00000000000000000000000000000001",
        format="parquet",
        storage_path="processed/bars.parquet",
        source="csv:data/raw/bars.csv",
        file_sha256=expected_sha256,
        byte_size=len(artifact_before),
        row_count=3,
        symbols=("AAPL", "MSFT"),
        earliest_timestamp=make_bar(minute=0).timestamp,
        latest_timestamp=make_bar(minute=5).timestamp,
        parquet_schema_version=1,
        registered_at=REGISTERED_AT,
    )
    assert record.unique_symbols == 2
    assert re.fullmatch(r"ds_[0-9a-f]{32}", record.dataset_id)
    assert catalog.get(record.dataset_id) == record
    assert catalog.list_records() == (record,)
    assert DatasetCatalog(catalog_path).list_records() == (record,)
    assert artifact_path.read_bytes() == artifact_before

    payload = load_json(catalog_path)
    serialized_record = payload["datasets"][0]
    assert payload["catalog_version"] == 1
    assert serialized_record["storage_path"] == "processed/bars.parquet"
    assert str(tmp_path) not in catalog_path.read_text(encoding="utf-8")
    assert serialized_record["registered_at"] == "2026-09-03T18:00:00+00:00"


def test_dataset_record_and_integrity_report_are_immutable(tmp_path: Path) -> None:
    artifact_path = tmp_path / "bars.parquet"
    write_dataset(artifact_path, [make_bar()])
    catalog = DatasetCatalog(tmp_path / "catalog.json")
    record = catalog.register_parquet(artifact_path, source="manual:test")
    report = catalog.verify(record.dataset_id)

    with pytest.raises(FrozenInstanceError):
        setattr(record, "source", "changed")
    with pytest.raises(FrozenInstanceError):
        setattr(report, "sha256_matches", False)
    assert isinstance(report, DatasetIntegrityReport)
    assert report.is_intact
    assert not hasattr(catalog, "update")
    assert not hasattr(catalog, "delete")


@pytest.mark.parametrize("source", ["", " ", "\t\n"])
def test_registration_rejects_blank_source_without_creating_catalog(
    tmp_path: Path, source: str
) -> None:
    artifact_path = tmp_path / "bars.parquet"
    write_dataset(artifact_path, [make_bar()])
    catalog_path = tmp_path / "catalog.json"

    with pytest.raises(ValueError, match="source must be a non-empty string"):
        DatasetCatalog(catalog_path).register_parquet(artifact_path, source=source)

    assert not catalog_path.exists()


def test_registration_rejects_non_string_source(tmp_path: Path) -> None:
    artifact_path = tmp_path / "bars.parquet"
    write_dataset(artifact_path, [make_bar()])

    with pytest.raises(TypeError, match="source must be a string"):
        DatasetCatalog(tmp_path / "catalog.json").register_parquet(
            artifact_path,
            source=42,  # type: ignore[arg-type]
        )


def test_registration_does_not_create_missing_catalog_parent(tmp_path: Path) -> None:
    artifact_path = tmp_path / "bars.parquet"
    write_dataset(artifact_path, [make_bar()])
    missing_parent = tmp_path / "catalogs"

    with pytest.raises(FileNotFoundError):
        DatasetCatalog(missing_parent / "catalog.json").register_parquet(
            artifact_path, source="manual:test"
        )

    assert not missing_parent.exists()


def test_empty_parquet_dataset_has_empty_summary(tmp_path: Path) -> None:
    artifact_path = tmp_path / "empty.parquet"
    write_dataset(artifact_path, [])

    record = DatasetCatalog(tmp_path / "catalog.json").register_parquet(
        artifact_path, source="manual:empty"
    )

    assert record.row_count == 0
    assert record.symbols == ()
    assert record.earliest_timestamp is None
    assert record.latest_timestamp is None


def test_same_path_and_fingerprint_registration_is_idempotent(tmp_path: Path) -> None:
    artifact_path = tmp_path / "bars.parquet"
    write_dataset(artifact_path, [make_bar()])
    catalog_path = tmp_path / "catalog.json"
    catalog = DatasetCatalog(catalog_path)
    first = catalog.register_parquet(artifact_path, source="manual:first")
    catalog_bytes = catalog_path.read_bytes()

    second = catalog.register_parquet(artifact_path, source="manual:second")

    assert second is not first
    assert second == first
    assert second.dataset_id == first.dataset_id
    assert second.source == "manual:first"
    assert catalog.list_records() == (first,)
    assert catalog_path.read_bytes() == catalog_bytes


def test_changed_artifact_at_registered_path_is_rejected_without_catalog_mutation(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "bars.parquet"
    store = write_dataset(artifact_path, [make_bar()])
    catalog_path = tmp_path / "catalog.json"
    catalog = DatasetCatalog(catalog_path)
    original_record = catalog.register_parquet(artifact_path, source="manual:first")
    catalog_bytes = catalog_path.read_bytes()
    store.write_bars([make_bar(symbol="MSFT")], overwrite=True)

    with pytest.raises(ValueError, match="registered dataset artifact has changed"):
        catalog.register_parquet(artifact_path, source="manual:second")

    assert catalog_path.read_bytes() == catalog_bytes
    assert catalog.get(original_record.dataset_id) == original_record


def test_identical_bytes_at_different_paths_receive_separate_ids(tmp_path: Path) -> None:
    first_path = tmp_path / "first.parquet"
    second_path = tmp_path / "second.parquet"
    write_dataset(first_path, [make_bar()])
    shutil.copyfile(first_path, second_path)
    catalog = DatasetCatalog(tmp_path / "catalog.json")

    first = catalog.register_parquet(first_path, source="manual:first")
    second = catalog.register_parquet(second_path, source="manual:second")

    assert first.file_sha256 == second.file_sha256
    assert first.dataset_id != second.dataset_id
    assert catalog.list_records() == (first, second)
    assert isinstance(catalog.list_records(), tuple)


def test_dataset_id_generation_retries_catalog_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identifiers = iter((UUID(int=1), UUID(int=1), UUID(int=2)))
    monkeypatch.setattr(catalog_module, "uuid4", lambda: next(identifiers))
    first_path = tmp_path / "first.parquet"
    second_path = tmp_path / "second.parquet"
    write_dataset(first_path, [make_bar()])
    write_dataset(second_path, [make_bar(symbol="MSFT")])
    catalog = DatasetCatalog(tmp_path / "catalog.json")

    first = catalog.register_parquet(first_path, source="manual:first")
    second = catalog.register_parquet(second_path, source="manual:second")

    assert first.dataset_id == "ds_00000000000000000000000000000001"
    assert second.dataset_id == "ds_00000000000000000000000000000002"


def test_relative_paths_remain_valid_when_catalog_tree_moves(tmp_path: Path) -> None:
    original_root = tmp_path / "original"
    artifact_path = original_root / "processed" / "bars.parquet"
    artifact_path.parent.mkdir(parents=True)
    write_dataset(artifact_path, [make_bar()])
    record = DatasetCatalog(original_root / "catalog.json").register_parquet(
        artifact_path, source="manual:portable"
    )
    moved_root = tmp_path / "moved"

    shutil.move(original_root, moved_root)
    moved_catalog = DatasetCatalog(moved_root / "catalog.json")

    assert moved_catalog.get(record.dataset_id).storage_path == "processed/bars.parquet"
    assert moved_catalog.verify(record.dataset_id).is_intact


def test_hashing_uses_bounded_chunks_and_records_exact_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_path = tmp_path / "bars.parquet"
    write_dataset(artifact_path, [make_bar(minute=minute) for minute in range(10)])
    expected_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    original_sha256 = hashlib.sha256
    update_sizes: list[int] = []

    class TrackingDigest:
        def __init__(self) -> None:
            self._digest = original_sha256()

        def update(self, chunk: bytes) -> None:
            update_sizes.append(len(chunk))
            self._digest.update(chunk)

        def hexdigest(self) -> str:
            return self._digest.hexdigest()

    monkeypatch.setattr(catalog_module, "_HASH_CHUNK_SIZE", 7)
    monkeypatch.setattr("quantforge.data.catalog.hashlib.sha256", TrackingDigest)

    record = DatasetCatalog(tmp_path / "catalog.json").register_parquet(
        artifact_path, source="manual:hash-test"
    )

    assert record.file_sha256 == expected_sha256
    assert record.byte_size == artifact_path.stat().st_size
    assert len(update_sizes) > 1
    assert max(update_sizes) <= 7


def test_verify_distinguishes_intact_modified_and_missing_artifacts(tmp_path: Path) -> None:
    artifact_path = tmp_path / "bars.parquet"
    write_dataset(artifact_path, [make_bar()])
    catalog = DatasetCatalog(tmp_path / "catalog.json")
    record = catalog.register_parquet(artifact_path, source="manual:test")

    intact = catalog.verify(record.dataset_id)
    artifact_bytes = bytearray(artifact_path.read_bytes())
    artifact_bytes[len(artifact_bytes) // 2] ^= 1
    artifact_path.write_bytes(artifact_bytes)
    modified = catalog.verify(record.dataset_id)
    artifact_path.unlink()
    missing = catalog.verify(record.dataset_id)

    assert intact == DatasetIntegrityReport(record.dataset_id, True, True, True)
    assert intact.is_intact
    assert modified == DatasetIntegrityReport(record.dataset_id, True, True, False)
    assert not modified.is_intact
    assert missing == DatasetIntegrityReport(record.dataset_id, False, False, False)
    assert not missing.is_intact


def test_unknown_dataset_id_raises_for_get_and_verify(tmp_path: Path) -> None:
    catalog = DatasetCatalog(tmp_path / "catalog.json")

    with pytest.raises(KeyError, match="unknown"):
        catalog.get("unknown")
    with pytest.raises(KeyError, match="unknown"):
        catalog.verify("unknown")


def test_invalid_json_and_invalid_utf8_catalogs_fail_without_resetting(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text("{not-json", encoding="utf-8")
    invalid_json = catalog_path.read_bytes()

    with pytest.raises(ValueError, match="invalid JSON") as json_error:
        DatasetCatalog(catalog_path).list_records()
    assert isinstance(json_error.value.__cause__, json.JSONDecodeError)
    assert catalog_path.read_bytes() == invalid_json

    catalog_path.write_bytes(b"\xff")
    invalid_utf8 = catalog_path.read_bytes()
    with pytest.raises(ValueError, match="not valid UTF-8") as utf8_error:
        DatasetCatalog(catalog_path).list_records()
    assert isinstance(utf8_error.value.__cause__, UnicodeDecodeError)
    assert catalog_path.read_bytes() == invalid_utf8


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"catalog_version": True, "datasets": []},
        {"catalog_version": 999, "datasets": []},
        {"catalog_version": 1, "datasets": {}},
        {"catalog_version": 1, "datasets": [{"dataset_id": "incomplete"}]},
    ],
    ids=["missing-structure", "boolean-version", "unsupported-version", "datasets", "record"],
)
def test_invalid_catalog_structure_fails_clearly(tmp_path: Path, payload: dict[str, Any]) -> None:
    catalog_path = tmp_path / "catalog.json"
    write_json(catalog_path, payload)

    with pytest.raises(ValueError):
        DatasetCatalog(catalog_path).list_records()


def test_duplicate_dataset_ids_in_catalog_fail_clearly(tmp_path: Path) -> None:
    first_path = tmp_path / "first.parquet"
    second_path = tmp_path / "second.parquet"
    write_dataset(first_path, [make_bar()])
    write_dataset(second_path, [make_bar(symbol="MSFT")])
    catalog_path = tmp_path / "catalog.json"
    catalog = DatasetCatalog(catalog_path)
    catalog.register_parquet(first_path, source="manual:first")
    catalog.register_parquet(second_path, source="manual:second")
    payload = load_json(catalog_path)
    datasets = cast(list[dict[str, Any]], payload["datasets"])
    datasets[1]["dataset_id"] = datasets[0]["dataset_id"]
    write_json(catalog_path, payload)

    with pytest.raises(ValueError, match="duplicate dataset_id"):
        DatasetCatalog(catalog_path).list_records()


def test_absolute_storage_path_in_catalog_is_rejected(tmp_path: Path) -> None:
    artifact_path = tmp_path / "bars.parquet"
    write_dataset(artifact_path, [make_bar()])
    catalog_path = tmp_path / "catalog.json"
    DatasetCatalog(catalog_path).register_parquet(artifact_path, source="manual:test")
    payload = load_json(catalog_path)
    datasets = cast(list[dict[str, Any]], payload["datasets"])
    datasets[0]["storage_path"] = str(artifact_path)
    write_json(catalog_path, payload)

    with pytest.raises(ValueError, match="storage_path must be relative"):
        DatasetCatalog(catalog_path).list_records()


def test_invalid_parquet_registration_preserves_existing_catalog_and_artifact(
    tmp_path: Path,
) -> None:
    valid_path = tmp_path / "valid.parquet"
    invalid_path = tmp_path / "invalid.parquet"
    write_dataset(valid_path, [make_bar()])
    invalid_path.write_bytes(b"not parquet")
    invalid_bytes = invalid_path.read_bytes()
    catalog_path = tmp_path / "catalog.json"
    catalog = DatasetCatalog(catalog_path)
    existing = catalog.register_parquet(valid_path, source="manual:valid")
    catalog_bytes = catalog_path.read_bytes()

    with pytest.raises(ValueError, match="corrupt or unreadable"):
        catalog.register_parquet(invalid_path, source="manual:invalid")

    assert catalog_path.read_bytes() == catalog_bytes
    assert invalid_path.read_bytes() == invalid_bytes
    assert catalog.list_records() == (existing,)


def test_failed_catalog_publication_preserves_previous_catalog_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_path = tmp_path / "first.parquet"
    second_path = tmp_path / "second.parquet"
    write_dataset(first_path, [make_bar()])
    write_dataset(second_path, [make_bar(symbol="MSFT")])
    catalog_path = tmp_path / "catalog.json"
    catalog = DatasetCatalog(catalog_path)
    existing = catalog.register_parquet(first_path, source="manual:first")
    catalog_bytes = catalog_path.read_bytes()
    artifact_bytes = second_path.read_bytes()

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError(f"cannot replace {source} with {destination}")

    monkeypatch.setattr("quantforge.data.catalog.os.replace", fail_replace)

    with pytest.raises(OSError, match="cannot replace"):
        catalog.register_parquet(second_path, source="manual:second")

    assert catalog_path.read_bytes() == catalog_bytes
    assert second_path.read_bytes() == artifact_bytes
    assert DatasetCatalog(catalog_path).list_records() == (existing,)
    assert list(tmp_path.glob(".catalog.json.*.tmp")) == []


def test_failed_catalog_serialization_preserves_previous_catalog_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_path = tmp_path / "first.parquet"
    second_path = tmp_path / "second.parquet"
    write_dataset(first_path, [make_bar()])
    write_dataset(second_path, [make_bar(symbol="MSFT")])
    catalog_path = tmp_path / "catalog.json"
    catalog = DatasetCatalog(catalog_path)
    existing = catalog.register_parquet(first_path, source="manual:first")
    catalog_bytes = catalog_path.read_bytes()

    def fail_dump(payload: object, destination: object, **kwargs: object) -> None:
        del payload, destination, kwargs
        raise TypeError("serialization failed")

    monkeypatch.setattr("quantforge.data.catalog.json.dump", fail_dump)

    with pytest.raises(TypeError, match="serialization failed"):
        catalog.register_parquet(second_path, source="manual:second")

    assert catalog_path.read_bytes() == catalog_bytes
    assert DatasetCatalog(catalog_path).list_records() == (existing,)
    assert list(tmp_path.glob(".catalog.json.*.tmp")) == []


def test_duplicate_and_out_of_order_data_can_be_cataloged_then_validated(
    tmp_path: Path,
) -> None:
    repeated = make_bar(minute=1)
    bars = [make_bar(minute=2), repeated, repeated]
    artifact_path = tmp_path / "bars.parquet"
    store = write_dataset(artifact_path, bars)
    catalog = DatasetCatalog(tmp_path / "catalog.json")

    record = catalog.register_parquet(artifact_path, source="manual:defects-allowed")
    report = MarketDataValidator().validate(store.iter_bars())

    assert record.row_count == 3
    assert [issue.code for issue in report.issues] == [
        "out_of_order_timestamp",
        "duplicate_observation",
        "out_of_order_timestamp",
    ]


def test_csv_to_parquet_to_catalog_integration(tmp_path: Path) -> None:
    csv_path = tmp_path / "bars.csv"
    csv_path.write_text(
        "\n".join(
            (
                "symbol,timestamp,open,high,low,close,volume",
                "MSFT,2026-09-01T13:31:00+00:00,200.0,205.0,195.0,202.0,2000",
                "AAPL,2026-09-01T09:30:00-04:00,100.0,105.0,95.0,102.0,1000",
            )
        ),
        encoding="utf-8",
    )
    artifact_path = tmp_path / "processed" / "bars.parquet"
    artifact_path.parent.mkdir()
    ParquetMarketDataStore(artifact_path).write_bars(CSVMarketDataProvider(csv_path).iter_bars())

    record = DatasetCatalog(tmp_path / "catalog.json").register_parquet(
        artifact_path, source="csv:bars.csv"
    )

    assert record.storage_path == "processed/bars.parquet"
    assert record.row_count == 2
    assert record.symbols == ("AAPL", "MSFT")
    assert record.earliest_timestamp == datetime(2026, 9, 1, 13, 30, tzinfo=UTC)
    assert record.latest_timestamp == datetime(2026, 9, 1, 13, 31, tzinfo=UTC)
