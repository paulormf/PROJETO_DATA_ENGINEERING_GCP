"""Plano deterministico para o fluxo API -> Dataflow -> Dataform.

Este modulo nao importa Airflow. Ele centraliza a convencao de nomes para que
retries do mesmo run reutilizem o mesmo lote logico e para que os caminhos do
GCS nao sejam digitados manualmente.
"""

from __future__ import annotations

from datetime import date
import hashlib
import re


# Airflow run ids normally contain ``:`` and ``+00:00`` in manual and
# scheduled runs. They are accepted here, while path separators, whitespace
# and control characters remain invalid because the value participates in
# deterministic object/job identifiers.
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,249}$")
_BUCKET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")


def _validate_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("execution_date deve usar YYYY-MM-DD") from exc


def _safe_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return token or "manual"


def build_api_batch_plan(
    *,
    execution_date: str,
    airflow_run_id: str,
    bucket_name: str,
    dataflow_template: str,
    dataflow_temp_location: str,
    bigquery_table: str,
    dead_letter_root: str,
) -> dict[str, str]:
    """Deriva todos os identificadores variaveis de uma execucao."""

    execution_date = _validate_date(execution_date)
    if not _RUN_ID_PATTERN.fullmatch(airflow_run_id):
        raise ValueError("airflow_run_id invalido")
    if not _BUCKET_PATTERN.fullmatch(bucket_name):
        raise ValueError("bucket_name invalido")
    if not dataflow_template.startswith("gs://"):
        raise ValueError("dataflow_template deve ser uma URI gs://")
    if not dataflow_temp_location.startswith("gs://"):
        raise ValueError("dataflow_temp_location deve ser uma URI gs://")
    if not dead_letter_root.startswith("gs://"):
        raise ValueError("dead_letter_root deve ser uma URI gs://")
    if not re.fullmatch(r"[^:]+:[^.]+\.[^.]+", bigquery_table):
        raise ValueError("bigquery_table deve usar projeto:dataset.tabela")

    token = _safe_token(airflow_run_id)
    digest = hashlib.sha256(airflow_run_id.encode("utf-8")).hexdigest()[:10]
    batch_id = f"api-{execution_date.replace('-', '')}-{token[:50]}-{digest}"[:128]
    object_name = (
        "raw/api=dummyjson/resource=products/"
        f"run={batch_id}/products.json"
    )
    dead_letter_prefix = (
        f"{dead_letter_root.rstrip('/')}/{execution_date}/" f"{batch_id}"
    )
    dataflow_job_name = f"api-products-{execution_date.replace('-', '')}-{digest}"

    return {
        "batch_id": batch_id,
        "object_name": object_name,
        "input_uri": f"gs://{bucket_name}/{object_name}",
        "dead_letter_output": dead_letter_prefix,
        "dataflow_job_name": dataflow_job_name,
        "dataflow_template": dataflow_template,
        "dataflow_temp_location": dataflow_temp_location,
        "bigquery_table": bigquery_table,
        "source_system": "dummyjson_products_api",
    }
