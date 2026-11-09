"""Executa full extract parametrizado e controlado do PostgreSQL para o GCS."""

from __future__ import annotations

import argparse
from datetime import date
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
from google.api_core.exceptions import PreconditionFailed
from psycopg import sql
from psycopg.rows import dict_row

from ingestion.ingestion_catalog import IngestionCatalog, TableSpec, load_catalog
from ingestion.cdc_epoch import CdcEpoch, build_cdc_epoch
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
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ingestion_date):
        raise ValueError("ingestion_date deve usar o formato ISO YYYY-MM-DD")
    ingestion_date = date.fromisoformat(ingestion_date).isoformat()
    _safe_run_id(batch_id)
    return (
        f"{bronze_prefix.rstrip('/')}/source=postgresql/schema={schema}/"
        f"table={table}/ingestion_date={ingestion_date}/batch_id={batch_id}"
    )


def _state_object(prefix: str) -> str:
    return f"{prefix}/checkpoint.json"


def _lock_object(prefix: str) -> str:
    return f"{prefix}/execution.lock"


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


def _acquire_execution_lock(bucket: storage.Bucket, prefix: str, run_id: str) -> tuple[storage.Blob, int]:
    """Adquire lock exclusivo por lote; locks abandonados exigem limpeza operacional."""
    lock = bucket.blob(_lock_object(prefix))
    try:
        lock.upload_from_string(
            json.dumps({"run_id": run_id, "acquired_at": _utc_now()}),
            content_type="application/json",
            if_generation_match=0,
        )
    except PreconditionFailed as exc:
        raise RuntimeError(
            "ja existe uma execucao para este lote ou um lock abandonado; "
            "confirme que o Cloud Run terminou antes da limpeza operacional"
        ) from exc
    if lock.generation is None:
        raise RuntimeError("GCS nao retornou generation para o lock da execucao")
    return lock, int(lock.generation)


def export_table_with_checkpoint(
    *,
    project_id: str,
    bucket_name: str,
    schema: str,
    table: TableSpec,
    bronze_prefix: str,
    run_id: str,
    ingestion_date: str | None = None,
    batch_size_override: int | None = None,
    cdc_epoch: CdcEpoch | None = None,
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
    if checkpoint is not None:
        raise RuntimeError(
            "o lote possui checkpoint sem manifest de sucesso. Para evitar misturar "
            "snapshots PostgreSQL diferentes, nao e seguro retomar esse prefixo; "
            "inicie uma nova execucao com outro run_id"
        )
    checkpoint = {
        "status": "started",
        "batch_id": batch_id,
        "run_id": run_id,
        "source": {"schema": schema, "table": table.name},
        "started_at": _utc_now(),
        "completed_parts": [],
        "rows": 0,
        "last_key": None,
    }
    completed_parts: list[dict[str, Any]] = []
    part_number = 0
    row_count = 0
    last_key = None
    schema_hint = None
    lock_blob, lock_generation = _acquire_execution_lock(bucket, prefix, run_id)
    try:
        checkpoint_generation = _write_json_object(
            bucket, checkpoint_name, checkpoint, None
        )
        with psycopg.connect(**_load_connection_kwargs()) as connection:
            connection.execute(
                "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            )
            with connection.cursor(row_factory=dict_row) as cursor:
                while True:
                    object_name = _part_object(prefix, part_number)
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
                        "completed_parts_count": len(completed_parts),
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
            "cdc_coordination": (
                {
                    "status": "coordinated",
                    "strategy": "cdc_first_replay",
                    "epoch_id": cdc_epoch.epoch_id,
                    "start_lsn": cdc_epoch.start_lsn,
                    "start_lsn_int": cdc_epoch.start_lsn_int,
                }
                if cdc_epoch is not None
                else {"status": "uncoordinated"}
            ),
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
            **{key: value for key, value in checkpoint.items() if key != "completed_parts"},
            "status": "failed",
            "updated_at": _utc_now(),
            "completed_parts_count": len(completed_parts),
            "rows": row_count,
            "last_key": last_key,
            "error_type": type(exc).__name__,
        }
        try:
            _write_json_object(bucket, checkpoint_name, failed_checkpoint, checkpoint_generation)
        except Exception:
            pass
        raise
    finally:
        # A hard termination can leave a lock behind. Never steal it automatically:
        # confirm the Cloud Run execution is terminal before operational cleanup.
        try:
            lock_blob.delete(if_generation_match=lock_generation)
        except Exception as lock_error:
            print(
                json.dumps(
                    {
                        "severity": "WARNING",
                        "message": "nao foi possivel liberar execution.lock",
                        "error_type": type(lock_error).__name__,
                        "object": _lock_object(prefix),
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )


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
    cdc_epoch: CdcEpoch | None = None,
) -> list[dict[str, Any]]:
    selected = [table for table in catalog.tables if table_name is None or table.name == table_name]
    if not selected:
        raise ValueError(f"tabela nao encontrada no catalogo: {table_name}")
    return [
        export_table_with_checkpoint(
            project_id=project_id,
            bucket_name=bucket_name,
            schema=catalog.schema,
            table=table,
            bronze_prefix=bronze_prefix,
            run_id=run_id,
            ingestion_date=ingestion_date,
            batch_size_override=batch_size_override,
            cdc_epoch=cdc_epoch,
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
    parser.add_argument("--cdc-epoch-id")
    parser.add_argument("--cdc-start-lsn")
    return parser.parse_args(argv)


def _resolve_ingestion_date(run_id: str, ingestion_date: str | None, *, generated: bool) -> str:
    if ingestion_date is not None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ingestion_date):
            raise ValueError("ingestion_date deve usar o formato ISO YYYY-MM-DD")
        return date.fromisoformat(ingestion_date).isoformat()
    match = re.search(r"(?<!\d)(\d{8})(?:T\d{6}Z|_)", run_id)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()
    if generated:
        return datetime.now(UTC).date().isoformat()
    raise ValueError(
        "ao reutilizar um run_id, informe --ingestion-date; "
        "ou use um run_id contendo a data YYYYMMDD"
    )


if __name__ == "__main__":
    arguments = parse_args(_normalize_argv(sys.argv[1:]))
    catalog = load_catalog(arguments.config)
    schema = arguments.schema or catalog.schema
    if schema != catalog.schema:
        raise ValueError("schema informado diverge do schema do catalogo")
    generated_run_id = arguments.run_id is None
    run_id = arguments.run_id or f"full_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    ingestion_date = _resolve_ingestion_date(
        run_id, arguments.ingestion_date, generated=generated_run_id
    )
    cdc_epoch = build_cdc_epoch(arguments.cdc_epoch_id, arguments.cdc_start_lsn)
    print(
        json.dumps(
            run_catalog(
                project_id=arguments.project_id,
                bucket_name=arguments.bucket_name,
                catalog=catalog,
                bronze_prefix=arguments.bronze_prefix,
                run_id=run_id,
                table_name=arguments.table,
                ingestion_date=ingestion_date,
                batch_size_override=arguments.batch_size,
                cdc_epoch=cdc_epoch,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )
