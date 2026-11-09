import json
from pathlib import Path

import pytest

from orchestration.composer.dags.materialization_plan import (
    TABLE_NAMES,
    build_materializer_overrides,
)


ROOT = Path(__file__).parents[2]


def test_dag_table_plan_matches_ingestion_catalog() -> None:
    catalog = json.loads(
        (ROOT / "config" / "ingestion_tables.json").read_text(encoding="utf-8")
    )
    catalog_tables = tuple(item["name"] for item in catalog["tables"])

    assert set(TABLE_NAMES) == set(catalog_tables)
    assert len(TABLE_NAMES) == len(catalog_tables)


def test_composer_templates_handle_empty_dag_run_conf() -> None:
    dag_source = (
        ROOT / "orchestration" / "composer" / "dags" /
        "ecommerce_bronze_materialization.py"
    ).read_text(encoding="utf-8")

    for key in ("project_id", "region", "materializer_job_name", "gcp_conn_id"):
        assert f"(dag_run.conf or {{}}).get('{key}'" in dag_source


def test_build_materializer_overrides_is_deterministic() -> None:
    overrides = build_materializer_overrides(
        ("categorias", "pedidos"),
        schema="ecommerce",
        run_id="full_20261109_001",
        ingestion_date="2026-11-09",
    )

    assert len(overrides) == 2
    assert "clear_args" not in overrides[0]["container_overrides"][0]
    assert overrides[0]["container_overrides"][0]["args"] == [
        "--schema",
        "ecommerce",
        "--table",
        "categorias",
        "--target-table",
        "bronze_categorias",
        "--run-id",
        "full_20261109_001",
        "--ingestion-date",
        "2026-11-09",
        "--bronze-prefix",
        "bronze/parquet",
    ]


@pytest.mark.parametrize(
    ("run_id", "ingestion_date"),
    [
        ("", "2026-11-09"),
        ("full/20261109", "2026-11-09"),
        ("full_20261109_001", "20261109"),
    ],
)
def test_build_materializer_overrides_rejects_invalid_cycle_values(
    run_id: str, ingestion_date: str
) -> None:
    with pytest.raises(ValueError):
        build_materializer_overrides(
            ("categorias",),
            schema="ecommerce",
            run_id=run_id,
            ingestion_date=ingestion_date,
        )
