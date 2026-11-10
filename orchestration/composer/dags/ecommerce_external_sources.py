"""Orquestracao futura das fontes externas do dominio ecommerce.

O DAG fica pausado por desenho: possui ``schedule=None`` e nao e enviado ao
Composer automaticamente pelo GitHub Actions. Quando o ambiente Composer for
reativado, uma execucao manual ou um agendamento controlado encadeara Cloud
Run, Dataflow Batch e Dataform.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.decorators import task
from airflow.models.param import Param
from airflow.providers.google.cloud.operators.cloud_run import (
    CloudRunExecuteJobOperator,
)
from airflow.providers.google.cloud.operators.dataflow import (
    DataflowStartFlexTemplateOperator,
)
from airflow.providers.google.cloud.operators.dataform import (
    DataformCreateWorkflowInvocationOperator,
)

from external_sources_plan import build_api_batch_plan


DAG_ID = "ecommerce_external_sources"


with DAG(
    dag_id=DAG_ID,
    description="API DummyJSON -> GCS Raw -> Dataflow Batch -> Dataform",
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
        "gcp_conn_id": Param("google_cloud_default", type="string"),
        "api_extract_job_name": Param("ecommerce-api-extract", type="string"),
        "bucket_name": Param(
            "botbrewpub-ghsurp-projeto-data-engineering-gcp", type="string"
        ),
        "dataflow_template": Param(
            "gs://botbrewpub-ghsurp-projeto-data-engineering-gcp/dataflow/templates/api-products/api-products-20261110-v2/template.json",
            type="string",
        ),
        "dataflow_temp_location": Param(
            "gs://botbrewpub-ghsurp-projeto-data-engineering-gcp/dataflow/temp/api-products",
            type="string",
        ),
        "dataflow_dead_letter_root": Param(
            "gs://botbrewpub-ghsurp-projeto-data-engineering-gcp/dataflow/dead-letter/api-products",
            type="string",
        ),
        "bigquery_table": Param(
            "botbrewpub-ghsurp:ecommerce_bronze.dummyjson_products_raw",
            type="string",
        ),
        "dataform_region": Param("us-central1", type="string"),
        "dataform_repository_id": Param("ecommerce-dataform-gcp", type="string"),
        "dataform_compilation_result": Param("", type="string"),
        "dataform_service_account": Param(
            "de-dataform-runner@botbrewpub-ghsurp.iam.gserviceaccount.com",
            type="string",
        ),
    },
    tags=["ecommerce", "api", "dataflow", "dataform", "manual"],
) as dag:

    @task(task_id="build_api_batch_plan")
    def build_plan() -> dict[str, str]:
        from airflow.operators.python import get_current_context

        context = get_current_context()
        dag_run = context["dag_run"]
        params = context["params"]
        return build_api_batch_plan(
            execution_date=str(context["ds"]),
            airflow_run_id=str(dag_run.run_id),
            bucket_name=str(params["bucket_name"]),
            dataflow_template=str(params["dataflow_template"]),
            dataflow_temp_location=str(params["dataflow_temp_location"]),
            bigquery_table=str(params["bigquery_table"]),
            dead_letter_root=str(params["dataflow_dead_letter_root"]),
        )

    batch_plan = build_plan()

    extract_api = CloudRunExecuteJobOperator(
        task_id="extract_api_to_gcs",
        project_id="{{ params.project_id }}",
        region="{{ params.region }}",
        job_name="{{ params.api_extract_job_name }}",
        gcp_conn_id="{{ params.gcp_conn_id }}",
        overrides={
            "container_overrides": [
                {
                    "args": [
                        "--project-id",
                        "{{ params.project_id }}",
                        "--bucket",
                        "{{ params.bucket_name }}",
                        "--object-name",
                        "{{ ti.xcom_pull(task_ids='build_api_batch_plan')['object_name'] }}",
                    ]
                }
            ]
        },
        polling_period_seconds=20,
        timeout_seconds=1800,
        deferrable=False,
    )

    run_dataflow = DataflowStartFlexTemplateOperator(
        task_id="normalize_api_with_dataflow",
        project_id="{{ params.project_id }}",
        location="{{ params.region }}",
        gcp_conn_id="{{ params.gcp_conn_id }}",
        append_job_name=False,
        wait_until_finished=True,
        deferrable=False,
        body={
            "launchParameter": {
                "jobName": "{{ ti.xcom_pull(task_ids='build_api_batch_plan')['dataflow_job_name'] }}",
                "containerSpecGcsPath": "{{ ti.xcom_pull(task_ids='build_api_batch_plan')['dataflow_template'] }}",
                "parameters": {
                    "input": "{{ ti.xcom_pull(task_ids='build_api_batch_plan')['input_uri'] }}",
                    "dead_letter_output": "{{ ti.xcom_pull(task_ids='build_api_batch_plan')['dead_letter_output'] }}",
                    "bigquery_table": "{{ ti.xcom_pull(task_ids='build_api_batch_plan')['bigquery_table'] }}",
                    "batch_id": "{{ ti.xcom_pull(task_ids='build_api_batch_plan')['batch_id'] }}",
                    "source_system": "{{ ti.xcom_pull(task_ids='build_api_batch_plan')['source_system'] }}",
                },
                "environment": {
                    "tempLocation": "{{ ti.xcom_pull(task_ids='build_api_batch_plan')['dataflow_temp_location'] }}"
                },
            }
        },
    )

    run_dataform = DataformCreateWorkflowInvocationOperator(
        task_id="transform_external_sources_with_dataform",
        project_id="{{ params.project_id }}",
        region="{{ params.dataform_region }}",
        repository_id="{{ params.dataform_repository_id }}",
        gcp_conn_id="{{ params.gcp_conn_id }}",
        workflow_invocation={
            "compilation_result": "{{ params.dataform_compilation_result }}",
            "invocation_config": {
                "service_account": "{{ params.dataform_service_account }}",
                "included_targets": [
                    {
                        "database": "{{ params.project_id }}",
                        "schema": "ecommerce_silver",
                        "name": "silver_dummyjson_products",
                    },
                    {
                        "database": "{{ params.project_id }}",
                        "schema": "ecommerce_silver",
                        "name": "silver_supplier_products",
                    },
                    {
                        "database": "{{ params.project_id }}",
                        "schema": "ecommerce_gold",
                        "name": "mart_catalogo_reconciliado",
                    },
                ],
            },
        },
        asynchronous=False,
        wait_time=15,
    )

    batch_plan >> extract_api >> run_dataflow >> run_dataform
