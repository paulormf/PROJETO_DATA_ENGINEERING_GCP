import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from materialization.bigquery_full_materializer import (
    build_manifest_object,
    build_staging_table_id,
    build_table_id,
    resolve_ingestion_date,
    validate_manifest,
)


def coordinated_manifest() -> dict[str, object]:
    return {
        "status": "succeeded",
        "run_id": "full_20261109_001",
        "source": {"schema": "ecommerce", "table": "categorias"},
        "cdc_coordination": {
            "status": "coordinated",
            "epoch_id": "epoch_20261109_001",
            "start_lsn": "1/71AC40C0",
        },
        "parts": [
            {"object": "part-00000.parquet", "rows": 70},
            {"object": "part-00001.parquet", "rows": 30},
        ],
        "rows": 100,
    }


def test_manifest_object_is_deterministic() -> None:
    assert build_manifest_object(
        bronze_prefix="bronze/parquet",
        schema="ecommerce",
        table="categorias",
        ingestion_date="2026-11-09",
        run_id="full_20261109_001",
    ) == (
        "bronze/parquet/source=postgresql/schema=ecommerce/table=categorias/"
        "ingestion_date=2026-11-09/batch_id=full_20261109_001__ecommerce__categorias/manifest.json"
    )


def test_manifest_validation_returns_explicit_parts_and_rows() -> None:
    objects, rows = validate_manifest(
        coordinated_manifest(),
        expected_schema="ecommerce",
        expected_table="categorias",
        expected_run_id="full_20261109_001",
    )

    assert objects == ["part-00000.parquet", "part-00001.parquet"]
    assert rows == 100


def test_manifest_validation_rejects_uncoordinated_load() -> None:
    manifest = coordinated_manifest()
    manifest["cdc_coordination"] = {"status": "uncoordinated"}

    with pytest.raises(ValueError, match="coordenados"):
        validate_manifest(
            manifest,
            expected_schema="ecommerce",
            expected_table="categorias",
            expected_run_id="full_20261109_001",
        )


def test_manifest_validation_rejects_row_mismatch() -> None:
    manifest = coordinated_manifest()
    manifest["rows"] = 99

    with pytest.raises(ValueError, match="contagem"):
        validate_manifest(
            manifest,
            expected_schema="ecommerce",
            expected_table="categorias",
            expected_run_id="full_20261109_001",
        )


def test_table_ids_are_deterministic() -> None:
    assert build_table_id(dataset="bronze", table="categorias") == "bronze.bronze_categorias"
    assert build_staging_table_id(
        dataset="bronze",
        schema="ecommerce",
        table="categorias",
        run_id="full_20261109_001",
    ) == "bronze.__stg_full_ecommerce_categorias_full_20261109_001"


def test_run_id_without_date_requires_ingestion_date() -> None:
    with pytest.raises(ValueError, match="ingestion_date"):
        resolve_ingestion_date("manual_run", None)
