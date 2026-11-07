from ingestion.full_extract_job import (
    _normalize_argv,
    _normalize_rows,
    _part_object,
    build_batch_prefix,
    build_batch_id,
)
from uuid import UUID


def test_build_batch_prefix_is_partitioned_by_batch() -> None:
    prefix = build_batch_prefix(
        bronze_prefix="bronze/parquet",
        schema="ecommerce",
        table="pedidos",
        ingestion_date="2026-11-07",
        batch_id=build_batch_id(
            run_id="full_20261107_001",
            schema="ecommerce",
            table="pedidos",
        ),
    )

    assert prefix.endswith(
        "table=pedidos/ingestion_date=2026-11-07/"
        "batch_id=full_20261107_001__ecommerce__pedidos"
    )


def test_part_object_has_stable_zero_padded_name() -> None:
    assert _part_object("bronze/batch", 12) == "bronze/batch/part-00012.parquet"


def test_normalize_argv_splits_cloud_run_single_argument_override() -> None:
    assert _normalize_argv(
        [
            "--schema=ecommerce --table=categorias --run-id=full_001",
        ]
    ) == [
        "--schema=ecommerce",
        "--table=categorias",
        "--run-id=full_001",
    ]


def test_normalize_rows_converts_uuid_and_json_values() -> None:
    rows = _normalize_rows(
        [
            {
                "session_id": UUID("61f16fad-60d5-a547-80b6-44107e634edf"),
                "event_data": {"source": "web", "value": 1},
            }
        ]
    )

    assert rows == [
        {
            "session_id": "61f16fad-60d5-a547-80b6-44107e634edf",
            "event_data": '{"source": "web", "value": 1}',
        }
    ]
