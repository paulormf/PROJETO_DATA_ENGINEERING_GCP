"""Executa full extract parametrizado e retomavel do PostgreSQL para o GCS."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shlex
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq
import psycopg
from google.cloud import storage
from psycopg import sql
from psycopg.rows import dict_row

from ingestion.ingestion_catalog import IngestionCatalog, TableSpec, load_catalog
from ingestion.postgres_gcs_exporter import _load_connection_kwargs, _utc_now, build_batch_id
from ingestion.postgres_parquet_exporter import validate_identifier


def _safe_run_id(run_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise ValueError("run_id deve conter somente letras, numeros, ponto, sublinhado ou hifen")
    return run_id


def build_batch_prefix(
    *, bronze_prefix: str, schema: str, table: str, ingestion_date: str, batch_id: str
) -> str:
    schema = validate_identifier(schema, "schema")
    table = validate_identifier(table, "tabela")
    _safe_run_id(batch_id)
    return (
        f"{bronze_prefix.rstrip('/')}/source=postgresql/schema={schema}/"
        f"table={table}/ingestion_date={ingestion_date}/batch_id={batch_id}"
    )


def _state_object(prefix: str) -> str:
    return f"{prefix}/checkpoint.json"


def _manifest_object(prefix: str) -> str:
    return f"{prefix}/manifest.json"


def _part_object(prefix: str, part_number: int) -> str:
    return f"{prefix}/part-{part_number:05d}.parquet"


def _read_json_object(bucket: storage.Bucket, object_name: str) -> tuple[dict[str, Any] | None, int | None]:
    blob = bucket.blob(object_name)
    if not blob.exists():
        return None, None
    blob.reload()
    payload = json.loads(blob.download_as_text())
    return payload, int(blob.generation) if blob.generation is not None else None


def _write_json_object(
    bucket: storage.Bucket,
    object_name: str,
    payload: dict[str, Any],
    generation: int | None,
) -> int | None:
    blob = bucket.blob(object_name)
    blob.upload_from_string(
        json.dumps(payload, indent=2, ensure_ascii=False),
        content_type="application/json",
        if_generation_match=0 if generation is None else generation,
    )
    return int(blob.generation) if blob.generation is not None else generation


def _load_schema_from_first_part(
    bucket: storage.Bucket, object_name: str
) -> pa.Schema | None:
    blob = bucket.blob(object_name)
    if not blob.exists():
        return None
    return pq.read_schema(io.BytesIO(blob.download_as_bytes()))


def _keyset_query(schema: str, table: str, primary_key: tuple[str, ...], last_key: list[Any] | None) -> tuple[sql.Composed, list[Any]]:
    identifiers = sql.SQL(", ").join(sql.Identifier(column) for column in primary_key)
    where = sql.SQL("")
    parameters: list[Any] = []
    if last_key is not None:
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in primary_key)
        where = sql.SQL(" WHERE ({}) > ({})").format(identifiers, placeholders)
        parameters.extend(last_key)
    query = sql.SQL("SELECT * FROM {}.{}{} ORDER BY {} LIMIT %s").format(
        sql.Identifier(schema), sql.Identifier(table), where, identifiers
    )
    return query, parameters


def _write_parquet_bytes(table: pa.Table) -> bytes:
    sink = io.BytesIO()
    pq.write_table(table, sink, compression="snappy")
    return sink.getvalue()


def _normalize_value(value: Any) -> Any:
    """Converte tipos PostgreSQL sem representacao estavel no PyArrow."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {column: _normalize_value(value) for column, value in row.items()}
        for row in rows
    ]


def _upload_part(
    bucket: storage.Bucket,
    object_name: str,
    table: pa.Table,
    last_key: list[Any],
) -> int:
    payload = _write_parquet_bytes(table)
    blob = bucket.blob(object_name)
    blob.metadata = {
        "rows": str(table.num_rows),
        "last_key": json.dumps(last_key, ensure_ascii=False, default=str),
    }
    blob.upload_from_string(
        payload,
        content_type="application/vnd.apache.parquet",
        if_generation_match=0,
    )
    return len(payload)


def _recover_uploaded_part(
    bucket: storage.Bucket, object_name: str, part_number: int
) -> dict[str, Any] | None:
    blob = bucket.blob(object_name)
    if not blob.exists():
        return None
    blob.reload()
    metadata = blob.metadata or {}
    if "rows" not in metadata or "last_key" not in metadata:
        raise RuntimeError(
            f"parte existente sem metadados de checkpoint: {object_name}"
        )
    return {
        "part": part_number,
        "object": object_name,
        "rows": int(metadata["rows"]),
        "bytes": int(blob.size or 0),
        "last_key": json.loads(metadata["last_key"]),
    }


def export_table_resumable(
    *,
    project_id: str,
    bucket_name: str,
    schema: str,
    table: TableSpec,
    bronze_prefix: str,
    run_id: str,
    ingestion_date: str | None = None,
    batch_size_override: int | None = None,
) -> dict[str, Any]:
    run_id = _safe_run_id(run_id)
    schema = validate_identifier(schema, "schema")
    ingestion_date = ingestion_date or datetime.now(UTC).date().isoformat()
    batch_id = build_batch_id(run_id=run_id, schema=schema, table=table.name)
    prefix = build_batch_prefix(
        bronze_prefix=bronze_prefix,
        schema=schema,
        table=table.name,
        ingestion_date=ingestion_date,
        batch_id=batch_id,
    )
    checkpoint_name = _state_object(prefix)
    manifest_name = _manifest_object(prefix)
    batch_size = batch_size_override or table.batch_size
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero")

    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    existing_manifest, _ = _read_json_object(bucket, manifest_name)
    if existing_manifest and existing_manifest.get("status") == "succeeded":
        return existing_manifest

    checkpoint, checkpoint_generation = _read_json_object(bucket, checkpoint_name)
    checkpoint = checkpoint or {
        "status": "started",
        "batch_id": batch_id,
        "run_id": run_id,
        "source": {"schema": schema, "table": table.name},
        "started_at": _utc_now(),
        "completed_parts": [],
        "rows": 0,
        "last_key": None,
    }
    checkpoint_generation = _write_json_object(
        bucket, checkpoint_name, checkpoint, checkpoint_generation
    )

    completed_parts = list(checkpoint.get("completed_parts", []))
    part_number = len(completed_parts)
    row_count = int(checkpoint.get("rows", 0))
    last_key = checkpoint.get("last_key")
    schema_hint = None
    if completed_parts:
        schema_hint = _load_schema_from_first_part(
            bucket, completed_parts[0]["object"]
        )

    try:
        with psycopg.connect(**_load_connection_kwargs()) as connection:
            connection.execute(
                "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            with connection.cursor(row_factory=dict_row) as cursor:
                while True:
                    object_name = _part_object(prefix, part_number)
                    recovered_part = _recover_uploaded_part(
                        bucket, object_name, part_number
                    )
                    if recovered_part is not None:
                        completed_parts.append(recovered_part)
                        row_count += recovered_part["rows"]
                        last_key = recovered_part["last_key"]
                        part_number += 1
                        checkpoint = {
                            "status": "running",
                            "batch_id": batch_id,
                            "run_id": run_id,
                            "source": {"schema": schema, "table": table.name},
                            "started_at": checkpoint["started_at"],
                            "updated_at": _utc_now(),
                            "completed_parts": completed_parts,
                            "rows": row_count,
                            "last_key": last_key,
                        }
                        checkpoint_generation = _write_json_object(
                            bucket, checkpoint_name, checkpoint, checkpoint_generation
                        )
                        continue

                    query, parameters = _keyset_query(
                        schema, table.name, table.primary_key, last_key
                    )
                    parameters.append(batch_size)
                    cursor.execute(query, parameters)
                    rows = cursor.fetchall()
                    if not rows:
                        break

                    normalized_rows = _normalize_rows(rows)
                    arrow_table = pa.Table.from_pylist(normalized_rows)
                    if schema_hint is None:
                        schema_hint = arrow_table.schema
                    else:
                        arrow_table = arrow_table.cast(schema_hint)
                    current_last_key = [row[column] for column in table.primary_key for row in [rows[-1]]]
                    part_bytes = _upload_part(
                        bucket, object_name, arrow_table, current_last_key
                    )
                    completed_parts.append(
                        {
                            "part": part_number,
                            "object": object_name,
                            "rows": arrow_table.num_rows,
                            "bytes": part_bytes,
                            "last_key": current_last_key,
                        }
                    )
                    row_count += arrow_table.num_rows
                    last_key = current_last_key
                    part_number += 1
                    checkpoint = {
                        "status": "running",
                        "batch_id": batch_id,
                        "run_id": run_id,
                        "source": {"schema": schema, "table": table.name},
                        "started_at": checkpoint["started_at"],
                        "updated_at": _utc_now(),
                        "completed_parts": completed_parts,
                        "rows": row_count,
                        "last_key": last_key,
                    }
                    checkpoint_generation = _write_json_object(
                        bucket, checkpoint_name, checkpoint, checkpoint_generation
                    )

        manifest = {
            "status": "succeeded",
            "batch_id": batch_id,
            "run_id": run_id,
            "ingestion_mode": "full",
            "source": {"schema": schema, "table": table.name},
            "object_prefix": prefix,
            "checkpoint_object": checkpoint_name,
            "parts": completed_parts,
            "rows": row_count,
            "batches": len(completed_parts),
            "started_at": checkpoint["started_at"],
            "finished_at": _utc_now(),
            "format": "parquet",
            "compression": "snappy",
        }
        _write_json_object(bucket, manifest_name, manifest, None)
        checkpoint["status"] = "succeeded"
        checkpoint["updated_at"] = manifest["finished_at"]
        _write_json_object(bucket, checkpoint_name, checkpoint, checkpoint_generation)
        return manifest
    except Exception as exc:
        failed_checkpoint = {
            **checkpoint,
            "status": "failed",
            "updated_at": _utc_now(),
            "completed_parts": completed_parts,
            "rows": row_count,
            "last_key": last_key,
            "error_type": type(exc).__name__,
        }
        try:
            _write_json_object(bucket, checkpoint_name, failed_checkpoint, checkpoint_generation)
        except Exception:
            pass
        raise


def run_catalog(
    *,
    project_id: str,
    bucket_name: str,
    catalog: IngestionCatalog,
    bronze_prefix: str,
    run_id: str,
    table_name: str | None = None,
    ingestion_date: str | None = None,
    batch_size_override: int | None = None,
) -> list[dict[str, Any]]:
    selected = [table for table in catalog.tables if table_name is None or table.name == table_name]
    if not selected:
        raise ValueError(f"tabela nao encontrada no catalogo: {table_name}")
    return [
        export_table_resumable(
            project_id=project_id,
            bucket_name=bucket_name,
            schema=catalog.schema,
            table=table,
            bronze_prefix=bronze_prefix,
            run_id=run_id,
            ingestion_date=ingestion_date,
            batch_size_override=batch_size_override,
        )
        for table in selected
    ]


def _normalize_argv(argv: list[str]) -> list[str]:
    """Aceita overrides do Cloud Run entregues como uma string unica."""
    if len(argv) == 1 and any(character.isspace() for character in argv[0]):
        return shlex.split(argv[0])
    return argv


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID"), required=not os.getenv("GCP_PROJECT_ID"))
    parser.add_argument("--bucket", dest="bucket_name", default=os.getenv("GCS_BUCKET"), required=not os.getenv("GCS_BUCKET"))
    parser.add_argument("--config", default="config/ingestion_tables.json")
    parser.add_argument("--schema")
    parser.add_argument("--table")
    parser.add_argument("--run-id", default=os.getenv("RUN_ID"))
    parser.add_argument("--ingestion-date")
    parser.add_argument("--bronze-prefix", default=os.getenv("GCS_BRONZE_PREFIX", "bronze/parquet"))
    parser.add_argument("--batch-size", type=int)
    return parser.parse_args(argv)


if __name__ == "__main__":
    arguments = parse_args(_normalize_argv(sys.argv[1:]))
    catalog = load_catalog(arguments.config)
    schema = arguments.schema or catalog.schema
    if schema != catalog.schema:
        raise ValueError("schema informado diverge do schema do catalogo")
    run_id = arguments.run_id or f"full_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    print(
        json.dumps(
            run_catalog(
                project_id=arguments.project_id,
                bucket_name=arguments.bucket_name,
                catalog=catalog,
                bronze_prefix=arguments.bronze_prefix,
                run_id=run_id,
                table_name=arguments.table,
                ingestion_date=arguments.ingestion_date,
                batch_size_override=arguments.batch_size,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )
