"""Exporta uma tabela PostgreSQL diretamente para um objeto Parquet no GCS."""

from __future__ import annotations

import argparse
import io
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

import pyarrow as pa
import pyarrow.parquet as pq
import psycopg
from dotenv import load_dotenv
from google.cloud import storage
from psycopg import sql
from psycopg.rows import dict_row

from ingestion.postgres_parquet_exporter import validate_identifier


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def build_object_names(
    *,
    bronze_prefix: str,
    schema: str,
    table: str,
    ingestion_date: str | None = None,
    batch_id: str | None = None,
) -> tuple[str, str, str]:
    """Gera o prefixo e os nomes dos objetos do lote."""
    schema = validate_identifier(schema, "schema")
    table = validate_identifier(table, "tabela")
    ingestion_date = ingestion_date or datetime.now(UTC).date().isoformat()
    batch_id = batch_id or str(uuid.uuid4())
    prefix = (
        f"{bronze_prefix.rstrip('/')}/source=postgresql/schema={schema}/"
        f"table={table}/ingestion_date={ingestion_date}/batch_id={batch_id}"
    )
    return prefix, f"{prefix}/part-00000.parquet", f"{prefix}/manifest.json"


def write_rows_to_parquet(rows: list[dict[str, Any]], sink: BinaryIO) -> tuple[int, int]:
    """Escreve um lote em um sink binário e retorna linhas e bytes lógico aproximado."""
    if not rows:
        return 0, 0
    table = pa.Table.from_pylist(rows)
    writer = pq.ParquetWriter(sink, table.schema, compression="snappy")
    try:
        writer.write_table(table)
    finally:
        writer.close()
    return table.num_rows, sink.tell() if hasattr(sink, "tell") else 0


def _load_connection_kwargs() -> dict[str, Any]:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    required = ("POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Variáveis ausentes no .env: " + ", ".join(missing))
    return {
        "host": os.environ["POSTGRES_HOST"],
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DBNAME", "appdb"),
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "row_factory": dict_row,
    }


def export_table_to_gcs(
    *,
    project_id: str,
    bucket_name: str,
    schema: str,
    table: str,
    bronze_prefix: str,
    ingestion_date: str | None = None,
    batch_id: str | None = None,
    batch_size: int = 10_000,
) -> dict[str, Any]:
    schema = validate_identifier(schema, "schema")
    table = validate_identifier(table, "tabela")
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero")

    object_prefix, parquet_object, manifest_object = build_object_names(
        bronze_prefix=bronze_prefix,
        schema=schema,
        table=table,
        ingestion_date=ingestion_date,
        batch_id=batch_id,
    )

    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    started_at = _utc_now()
    row_count = 0
    batch_count = 0

    parquet_blob = bucket.blob(parquet_object)
    with parquet_blob.open(
        mode="wb",
        chunk_size=8 * 1024 * 1024,
        content_type="application/vnd.apache.parquet",
        if_generation_match=0,
    ) as sink:
        with psycopg.connect(**_load_connection_kwargs()) as connection:
            connection.execute(
                "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            with connection.cursor(name=f"gcs_export_{table}") as cursor:
                cursor.execute(
                    sql.SQL("SELECT * FROM {}.{} ORDER BY 1").format(
                        sql.Identifier(schema), sql.Identifier(table)
                    )
                )
                first_rows = cursor.fetchmany(batch_size)
                if not first_rows:
                    raise ValueError("A tabela não possui registros para exportação")
                first_table = pa.Table.from_pylist(first_rows)
                writer = pq.ParquetWriter(sink, first_table.schema, compression="snappy")
                try:
                    writer.write_table(first_table)
                    row_count += first_table.num_rows
                    batch_count += 1
                    while rows := cursor.fetchmany(batch_size):
                        next_table = pa.Table.from_pylist(rows).cast(first_table.schema)
                        writer.write_table(next_table)
                        row_count += next_table.num_rows
                        batch_count += 1
                finally:
                    writer.close()

    manifest = {
        "status": "succeeded",
        "source": {"schema": schema, "table": table},
        "object_prefix": object_prefix,
        "rows": row_count,
        "batches": batch_count,
        "parquet_object": parquet_object,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "format": "parquet",
        "compression": "snappy",
    }
    bucket.blob(manifest_object).upload_from_string(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        content_type="application/json",
        if_generation_match=0,
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID"), required=not os.getenv("GCP_PROJECT_ID"))
    parser.add_argument("--bucket", dest="bucket_name", default=os.getenv("GCS_BUCKET"), required=not os.getenv("GCS_BUCKET"))
    parser.add_argument("--schema", default="ecommerce")
    parser.add_argument("--table", default="categorias")
    parser.add_argument("--bronze-prefix", default=os.getenv("GCS_BRONZE_PREFIX", "bronze/parquet"))
    parser.add_argument("--ingestion-date")
    parser.add_argument("--batch-id")
    parser.add_argument("--batch-size", type=int, default=10_000)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(export_table_to_gcs(**vars(parse_args())), indent=2, ensure_ascii=False))
