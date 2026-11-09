"""Materializa uma tabela full do GCS em uma tabela Bronze do BigQuery.

O job trabalha uma tabela por vez para permitir tarefas independentes no
Composer. O manifesto e a unidade de controle: somente um manifesto full
coordenado e concluido pode ser carregado. O Parquet e carregado primeiro em
staging; depois a particao logica do mesmo ``run_id`` e substituida em uma
transacao BigQuery, tornando reexecucoes idempotentes.
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import json
import os
import re
from typing import Any, Iterable

from ingestion.ingestion_catalog import load_catalog


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,299}$")
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def validate_identifier(value: str, field_name: str) -> str:
    """Valida identificadores usados em nomes de objetos e tabelas."""

    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} invalido: {value!r}")
    return value


def validate_run_id(run_id: str) -> str:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("run_id deve conter somente letras, numeros, ponto, sublinhado ou hifen")
    return run_id


def resolve_ingestion_date(run_id: str, ingestion_date: str | None) -> str:
    """Resolve a data do prefixo sem depender do relogio do worker."""

    validate_run_id(run_id)
    if ingestion_date is not None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ingestion_date):
            raise ValueError("ingestion_date deve usar o formato ISO YYYY-MM-DD")
        return date.fromisoformat(ingestion_date).isoformat()

    match = re.search(r"(?<!\d)(\d{8})(?:T\d{6}Z|_)", run_id)
    if match is None:
        raise ValueError(
            "informe ingestion_date quando o run_id nao contiver uma data YYYYMMDD"
        )
    return datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()


def build_manifest_object(
    *,
    bronze_prefix: str,
    schema: str,
    table: str,
    ingestion_date: str,
    run_id: str,
) -> str:
    """Monta o caminho deterministico do manifesto, sem exigir URI manual."""

    validate_identifier(schema, "schema")
    validate_identifier(table, "tabela")
    validate_run_id(run_id)
    ingestion_date = resolve_ingestion_date(run_id, ingestion_date)
    batch_id = f"{run_id}__{schema}__{table}"
    return (
        f"{bronze_prefix.rstrip('/')}/source=postgresql/schema={schema}/"
        f"table={table}/ingestion_date={ingestion_date}/batch_id={batch_id}/manifest.json"
    )


def validate_manifest(
    manifest: dict[str, Any],
    *,
    expected_schema: str,
    expected_table: str,
    expected_run_id: str,
) -> tuple[list[str], int]:
    """Valida o contrato minimo antes de iniciar um load job BigQuery."""

    if manifest.get("status") != "succeeded":
        raise ValueError("manifesto nao possui status=succeeded")
    if manifest.get("run_id") != expected_run_id:
        raise ValueError("run_id do manifesto diverge do run_id solicitado")

    source = manifest.get("source") or {}
    if source.get("schema") != expected_schema or source.get("table") != expected_table:
        raise ValueError("origem do manifesto diverge da tabela solicitada")

    coordination = manifest.get("cdc_coordination") or {}
    if coordination.get("status") != "coordinated":
        raise ValueError("somente manifestos full coordenados podem ser materializados")
    if not coordination.get("epoch_id") or not coordination.get("start_lsn"):
        raise ValueError("manifesto coordenado sem epoch_id ou start_lsn")

    parts = manifest.get("parts") or []
    objects: list[str] = []
    part_rows = 0
    for part in parts:
        object_name = part.get("object")
        if not isinstance(object_name, str) or not object_name:
            raise ValueError("manifesto possui parte sem object")
        if object_name in objects:
            raise ValueError("manifesto possui objetos Parquet duplicados")
        objects.append(object_name)
        part_rows += int(part.get("rows", 0))

    if not objects:
        raise ValueError("manifesto nao possui partes Parquet")
    declared_rows = int(manifest.get("rows", -1))
    if part_rows != declared_rows:
        raise ValueError(
            f"contagem do manifesto diverge das partes: manifest={declared_rows}, parts={part_rows}"
        )
    return objects, declared_rows


def build_table_id(*, dataset: str, table: str) -> str:
    validate_identifier(dataset, "dataset")
    validate_identifier(table, "tabela")
    return f"{dataset}.bronze_{table}"


def build_staging_table_id(*, dataset: str, schema: str, table: str, run_id: str) -> str:
    validate_identifier(dataset, "dataset")
    validate_identifier(schema, "schema")
    validate_identifier(table, "tabela")
    validate_run_id(run_id)
    safe_run_id = re.sub(r"[^A-Za-z0-9_]", "_", run_id)
    return f"{dataset}.__stg_full_{schema}_{table}_{safe_run_id}"


def _quote_table(project_id: str, table_id: str) -> str:
    return f"`{project_id}.{table_id}`"


def _quote_columns(columns: Iterable[str]) -> str:
    validated = [validate_identifier(column, "coluna") for column in columns]
    if not validated:
        raise ValueError("ao menos uma coluna e necessaria para clustering")
    return ", ".join(f"`{column}`" for column in validated)


def _read_manifest(*, storage_client: Any, bucket_name: str, object_name: str) -> dict[str, Any]:
    blob = storage_client.bucket(bucket_name).blob(object_name)
    return json.loads(blob.download_as_text())


def _query_parameters(
    *,
    bigquery_module: Any,
    run_id: str,
    schema: str,
    table: str,
    epoch_id: str,
    start_lsn: str,
    ingestion_date: str,
) -> list[Any]:
    return [
        bigquery_module.ScalarQueryParameter("run_id", "STRING", run_id),
        bigquery_module.ScalarQueryParameter("source_schema", "STRING", schema),
        bigquery_module.ScalarQueryParameter("source_table", "STRING", table),
        bigquery_module.ScalarQueryParameter("epoch_id", "STRING", epoch_id),
        bigquery_module.ScalarQueryParameter("start_lsn", "STRING", start_lsn),
        bigquery_module.ScalarQueryParameter("ingestion_date", "DATE", ingestion_date),
    ]


def materialize_full_table(
    *,
    project_id: str,
    bucket_name: str,
    bronze_prefix: str,
    dataset: str,
    schema: str,
    table: str,
    primary_key: tuple[str, ...],
    run_id: str,
    ingestion_date: str | None = None,
    delete_staging_on_success: bool = True,
) -> dict[str, Any]:
    """Carrega uma tabela full coordenada em BigQuery Bronze."""

    from google.cloud import bigquery, storage

    validate_run_id(run_id)
    validate_identifier(schema, "schema")
    validate_identifier(table, "tabela")
    ingestion_date = resolve_ingestion_date(run_id, ingestion_date)
    manifest_object = build_manifest_object(
        bronze_prefix=bronze_prefix,
        schema=schema,
        table=table,
        ingestion_date=ingestion_date,
        run_id=run_id,
    )

    storage_client = storage.Client(project=project_id)
    manifest = _read_manifest(
        storage_client=storage_client,
        bucket_name=bucket_name,
        object_name=manifest_object,
    )
    objects, expected_rows = validate_manifest(
        manifest,
        expected_schema=schema,
        expected_table=table,
        expected_run_id=run_id,
    )

    bigquery_client = bigquery.Client(project=project_id)
    staging_table_id = build_staging_table_id(
        dataset=dataset,
        schema=schema,
        table=table,
        run_id=run_id,
    )
    final_table_id = build_table_id(dataset=dataset, table=table)
    staging_ref = f"{project_id}.{staging_table_id}"
    final_ref = f"{project_id}.{final_table_id}"
    uris = [f"gs://{bucket_name}/{object_name}" for object_name in objects]

    load_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        autodetect=True,
    )
    load_job = bigquery_client.load_table_from_uri(uris, staging_ref, job_config=load_config)
    load_job.result()

    count_query = (
        f"SELECT COUNT(*) AS row_count FROM {_quote_table(project_id, staging_table_id)}"
    )
    count_row = next(iter(bigquery_client.query(count_query).result()))
    loaded_rows = int(count_row[0])
    if loaded_rows != expected_rows:
        raise RuntimeError(
            f"contagem BigQuery diverge do manifesto: manifest={expected_rows}, loaded={loaded_rows}"
        )

    coordination = manifest["cdc_coordination"]
    parameters = _query_parameters(
        bigquery_module=bigquery,
        run_id=run_id,
        schema=schema,
        table=table,
        epoch_id=coordination["epoch_id"],
        start_lsn=coordination["start_lsn"],
        ingestion_date=ingestion_date,
    )
    query_config = bigquery.QueryJobConfig(query_parameters=parameters)
    metadata_select = """
        s.*,
        @run_id AS _ingestion_run_id,
        'full' AS _ingestion_mode,
        @source_schema AS _source_schema,
        @source_table AS _source_table,
        @epoch_id AS _cdc_epoch_id,
        @start_lsn AS _cdc_start_lsn,
        CURRENT_TIMESTAMP() AS _ingested_at,
        @ingestion_date AS _ingestion_date
    """
    cluster_columns = _quote_columns(primary_key)
    create_query = f"""
        CREATE TABLE IF NOT EXISTS {_quote_table(project_id, final_table_id)}
        PARTITION BY _ingestion_date
        CLUSTER BY {cluster_columns}
        AS
        SELECT {metadata_select}
        FROM {_quote_table(project_id, staging_table_id)} AS s
        WHERE FALSE
    """
    bigquery_client.query(create_query, job_config=query_config).result()

    publish_query = f"""
        BEGIN TRANSACTION;
        DELETE FROM {_quote_table(project_id, final_table_id)}
        WHERE _ingestion_run_id = @run_id
          AND _source_schema = @source_schema
          AND _source_table = @source_table;
        INSERT INTO {_quote_table(project_id, final_table_id)}
        SELECT {metadata_select}
        FROM {_quote_table(project_id, staging_table_id)} AS s;
        COMMIT TRANSACTION;
    """
    bigquery_client.query(publish_query, job_config=query_config).result()

    final_count_query = f"""
        SELECT COUNT(*) AS row_count
        FROM {_quote_table(project_id, final_table_id)}
        WHERE _ingestion_run_id = @run_id
          AND _source_schema = @source_schema
          AND _source_table = @source_table
    """
    final_count_row = next(
        iter(bigquery_client.query(final_count_query, job_config=query_config).result())
    )
    published_rows = int(final_count_row[0])
    if published_rows != expected_rows:
        raise RuntimeError(
            f"contagem Bronze diverge do manifesto: manifest={expected_rows}, published={published_rows}"
        )

    if delete_staging_on_success:
        bigquery_client.delete_table(staging_ref, not_found_ok=True)

    return {
        "status": "succeeded",
        "project_id": project_id,
        "dataset": dataset,
        "source": {"schema": schema, "table": table},
        "run_id": run_id,
        "manifest_object": manifest_object,
        "staging_table": staging_ref,
        "bronze_table": final_ref,
        "rows": published_rows,
        "parts": len(objects),
        "cdc_epoch_id": coordination["epoch_id"],
        "cdc_start_lsn": coordination["start_lsn"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID"), required=not os.getenv("GCP_PROJECT_ID"))
    parser.add_argument("--bucket", dest="bucket_name", default=os.getenv("GCS_BUCKET"), required=not os.getenv("GCS_BUCKET"))
    parser.add_argument("--dataset", default=os.getenv("BQ_BRONZE_DATASET"), required=not os.getenv("BQ_BRONZE_DATASET"))
    parser.add_argument("--schema", default="ecommerce")
    parser.add_argument("--table", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--ingestion-date")
    parser.add_argument("--bronze-prefix", default=os.getenv("GCS_BRONZE_PREFIX", "bronze/parquet"))
    parser.add_argument("--config", default="config/ingestion_tables.json")
    return parser.parse_args(argv)


if __name__ == "__main__":
    arguments = parse_args()
    catalog = load_catalog(arguments.config)
    if arguments.schema != catalog.schema:
        raise ValueError("schema informado diverge do schema do catalogo")
    table_spec = next((item for item in catalog.tables if item.name == arguments.table), None)
    if table_spec is None:
        raise ValueError(f"tabela nao encontrada no catalogo: {arguments.table}")
    print(
        json.dumps(
            materialize_full_table(
                project_id=arguments.project_id,
                bucket_name=arguments.bucket_name,
                bronze_prefix=arguments.bronze_prefix,
                dataset=arguments.dataset,
                schema=arguments.schema,
                table=table_spec.name,
                primary_key=table_spec.primary_key,
                run_id=arguments.run_id,
                ingestion_date=arguments.ingestion_date,
            ),
            indent=2,
            ensure_ascii=False,
        )
    )
