from __future__ import annotations

import pytest

from orchestration.composer.dags.external_sources_plan import build_api_batch_plan


COMMON_ARGS = {
    "execution_date": "2026-11-10",
    "bucket_name": "botbrewpub-ghsurp-projeto-data-engineering-gcp",
    "dataflow_template": (
        "gs://botbrewpub-ghsurp-projeto-data-engineering-gcp/"
        "dataflow/templates/api-products/template.json"
    ),
    "dataflow_temp_location": (
        "gs://botbrewpub-ghsurp-projeto-data-engineering-gcp/dataflow/temp/api-products"
    ),
    "bigquery_table": "botbrewpub-ghsurp:ecommerce_bronze.dummyjson_products_raw",
    "dead_letter_root": (
        "gs://botbrewpub-ghsurp-projeto-data-engineering-gcp/"
        "dataflow/dead-letter/api-products"
    ),
}


def test_plan_accepts_real_airflow_manual_run_id() -> None:
    plan = build_api_batch_plan(
        **COMMON_ARGS,
        airflow_run_id="manual__2026-11-10T16:23:04.036145+00:00",
    )

    assert plan["batch_id"].startswith("api-20261110-manual-2026-11-10t16-23-04")
    assert plan["object_name"].endswith(f"run={plan['batch_id']}/products.json")
    assert plan["input_uri"].startswith("gs://botbrewpub-ghsurp-projeto-data-engineering-gcp/")
    assert plan["dataflow_job_name"].startswith("api-products-20261110-")


def test_same_airflow_run_produces_same_plan() -> None:
    first = build_api_batch_plan(
        **COMMON_ARGS,
        airflow_run_id="scheduled__2026-11-10T03:00:00+00:00",
    )
    second = build_api_batch_plan(
        **COMMON_ARGS,
        airflow_run_id="scheduled__2026-11-10T03:00:00+00:00",
    )

    assert first == second


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("airflow_run_id", "manual/unsafe"),
        ("bucket_name", "Bucket-With-Uppercase"),
        ("dataflow_template", "https://example.invalid/template.json"),
        ("dataflow_temp_location", "dataflow-temp"),
        ("bigquery_table", "project.dataset.table"),
        ("dead_letter_root", "bucket/dlq"),
    ],
)
def test_plan_rejects_invalid_runtime_values(field: str, value: str) -> None:
    arguments = dict(COMMON_ARGS)
    arguments[field] = value
    airflow_run_id = arguments.pop(
        "airflow_run_id", "manual__2026-11-10T16:23:04+00:00"
    )

    with pytest.raises(ValueError):
        build_api_batch_plan(
            airflow_run_id=airflow_run_id,
            **arguments,
        )
