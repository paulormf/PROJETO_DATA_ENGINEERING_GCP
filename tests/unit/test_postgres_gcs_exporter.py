import io

import pyarrow.parquet as pq

from ingestion.postgres_gcs_exporter import (
    build_batch_id,
    build_object_names,
    parse_args,
    write_rows_to_parquet,
)


def test_write_rows_to_parquet_uses_snappy_and_preserves_rows() -> None:
    sink = io.BytesIO()

    rows, _ = write_rows_to_parquet(
        [{"categoria_id": 1, "nome_categoria": "Casa"}],
        sink,
    )

    assert rows == 1
    sink.seek(0)
    parquet_file = pq.ParquetFile(sink)
    assert parquet_file.metadata.num_rows == 1
    assert parquet_file.metadata.row_group(0).column(0).compression == "SNAPPY"


def test_write_rows_to_parquet_ignores_empty_batch() -> None:
    sink = io.BytesIO()
    assert write_rows_to_parquet([], sink) == (0, 0)
    assert sink.getvalue() == b""


def test_cli_bucket_maps_to_bucket_name(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "postgres_gcs_exporter",
            "--project-id",
            "project",
            "--bucket",
            "bucket",
            "--schema",
            "ecommerce",
            "--table",
            "categorias",
            "--bronze-prefix",
            "bronze/parquet",
        ],
    )

    arguments = parse_args()

    assert arguments.bucket_name == "bucket"


def test_cli_reads_project_and_bucket_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "project-from-env")
    monkeypatch.setenv("GCS_BUCKET", "bucket-from-env")
    monkeypatch.setattr(
        "sys.argv",
        [
            "postgres_gcs_exporter",
            "--schema",
            "ecommerce",
            "--table",
            "categorias",
            "--bronze-prefix",
            "bronze/parquet",
        ],
    )

    arguments = parse_args()

    assert arguments.project_id == "project-from-env"
    assert arguments.bucket_name == "bucket-from-env"


def test_build_object_names_generates_partitioned_paths() -> None:
    prefix, parquet_object, manifest_object = build_object_names(
        bronze_prefix="bronze/parquet/",
        schema="ecommerce",
        table="categorias",
        ingestion_date="2026-11-07",
        batch_id="batch-123",
    )

    assert prefix == (
        "bronze/parquet/source=postgresql/schema=ecommerce/"
        "table=categorias/ingestion_date=2026-11-07/batch_id=batch-123"
    )
    assert parquet_object.endswith("/part-00000.parquet")
    assert manifest_object.endswith("/manifest.json")


def test_build_batch_id_is_deterministic_for_run_and_table() -> None:
    assert build_batch_id(
        run_id="full_20261107_001",
        schema="ecommerce",
        table="categorias",
    ) == "full_20261107_001__ecommerce__categorias"


def test_build_batch_id_rejects_unsafe_run_id() -> None:
    try:
        build_batch_id(run_id="full/20261107", schema="ecommerce", table="categorias")
    except ValueError as exc:
        assert "run_id" in str(exc)
    else:
        raise AssertionError("run_id inseguro deveria ser rejeitado")


def test_cli_accepts_run_id(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "postgres_gcs_exporter",
            "--project-id",
            "project",
            "--bucket",
            "bucket",
            "--run-id",
            "full_20261107_001",
        ],
    )

    arguments = parse_args()

    assert arguments.run_id == "full_20261107_001"
