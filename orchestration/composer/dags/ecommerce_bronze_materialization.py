"""DAG Composer para materializacao full da Bronze por tabela.

O fluxo usa um unico Cloud Run Job reutilizavel e cria uma tarefa mapeada para
cada tabela do catalogo. A carga full e o consumidor CDC sao etapas distintas;
esta DAG recebe um ``run_id`` ja publicado no GCS e materializa somente aquele
ciclo coordenado no BigQuery.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.decorators import task
from airflow.models.param import Param
from airflow.providers.google.cloud.operators.cloud_run import (
    CloudRunExecuteJobOperator,
)

from materialization_plan import TABLE_NAMES, build_materializer_overrides


DAG_ID = "ecommerce_bronze_materialization"
DEFAULT_RUN_ID = "full_20261109_001"
DEFAULT_INGESTION_DATE = "2026-11-09"
MAX_MATERIALIZATION_CONCURRENCY = 4


def _dag_run_value(context: dict, key: str) -> str:
    """Permite override seguro via dag_run.conf sem depender de segredo."""

    dag_run = context.get("dag_run")
    runtime_conf = getattr(dag_run, "conf", None) or {}
    params = context["params"]
    return str(runtime_conf.get(key, params[key]))


with DAG(
    dag_id=DAG_ID,
    description="Materializa o ciclo full coordenado em tabelas Bronze do BigQuery",
    start_date=datetime(2026, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data-platform",
        "depends_on_past": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    params={
        "project_id": Param("botbrewpub-ghsurp", type="string"),
        "region": Param("us-central1", type="string"),
        "materializer_job_name": Param(
            "ecommerce-bronze-materializer", type="string"
        ),
        "gcp_conn_id": Param("google_cloud_default", type="string"),
        "schema": Param("ecommerce", type="string"),
        "run_id": Param(DEFAULT_RUN_ID, type="string"),
        "ingestion_date": Param(DEFAULT_INGESTION_DATE, type="string"),
        "bronze_prefix": Param("bronze/parquet", type="string"),
    },
    tags=["ecommerce", "bronze", "cloud-run", "materialization"],
) as dag:

    @task(task_id="build_materialization_plan")
    def build_plan() -> list[dict]:
        from airflow.operators.python import get_current_context

        context = get_current_context()
        return build_materializer_overrides(
            TABLE_NAMES,
            schema=_dag_run_value(context, "schema"),
            run_id=_dag_run_value(context, "run_id"),
            ingestion_date=_dag_run_value(context, "ingestion_date"),
            bronze_prefix=_dag_run_value(context, "bronze_prefix"),
        )

    materialization_plan = build_plan()

    materialize_table = (
        CloudRunExecuteJobOperator.partial(
            task_id="materialize_table",
            project_id="{{ (dag_run.conf or {}).get('project_id', params.project_id) }}",
            region="{{ (dag_run.conf or {}).get('region', params.region) }}",
            job_name="{{ (dag_run.conf or {}).get('materializer_job_name', params.materializer_job_name) }}",
            gcp_conn_id="{{ (dag_run.conf or {}).get('gcp_conn_id', params.gcp_conn_id) }}",
            polling_period_seconds=20,
            timeout_seconds=4000,
            deferrable=False,
            max_active_tis_per_dag=MAX_MATERIALIZATION_CONCURRENCY,
        )
        .expand(overrides=materialization_plan)
    )

    materialization_plan >> materialize_table
