from __future__ import annotations

from apache_beam.testing.test_pipeline import TestPipeline as BeamTestPipeline
from apache_beam.testing.util import assert_that, equal_to

import apache_beam as beam

from dataflow.supplier_products_batch import (
    BIGQUERY_SCHEMA,
    INVALID_TAG,
    VALID_TAG,
    NormalizeSupplierProduct,
    build_bigquery_row,
    normalize_supplier_product,
    parse_csv_line,
)


def test_parse_csv_line_supports_quoted_commas() -> None:
    record = parse_csv_line(
        'SUP-001,SKU-001,"Cafe, torrado",Bebidas,Marca,12.50,10,2026-11-10'
    )

    assert record["product_name"] == "Cafe, torrado"
    assert record["price"] == "12.50"


def test_normalize_supplier_product_preserves_decimal_as_text() -> None:
    result_type, result = normalize_supplier_product(
        {
            "supplier_product_id": "SUP-001",
            "sku": "SKU-001",
            "product_name": "Cafe torrado",
            "category": "Bebidas",
            "brand": "Marca",
            "price": "12.50",
            "stock_quantity": "10",
            "source_updated_at": "2026-11-10T00:00:00Z",
        },
        source_system="supplier_csv",
        batch_id="batch-001",
        ingested_at="2026-11-10T12:00:00+00:00",
    )

    assert result_type == VALID_TAG
    assert result["price"] == "12.50"
    assert result["stock_quantity"] == 10
    assert len(result["record_hash"]) == 64


def test_normalize_supplier_product_sends_invalid_record_to_dlq_contract() -> None:
    result_type, result = normalize_supplier_product(
        {
            "supplier_product_id": "SUP-002",
            "sku": "",
            "product_name": "Produto inválido",
            "category": "Bebidas",
            "brand": "Marca",
            "price": "not-a-number",
            "stock_quantity": "-1",
            "source_updated_at": "2026-11-10T00:00:00Z",
        },
        source_system="supplier_csv",
        batch_id="batch-001",
        ingested_at="2026-11-10T12:00:00+00:00",
    )

    assert result_type == INVALID_TAG
    assert "sku is required" in result["error_reason"]
    assert "price must be a decimal" in result["error_reason"]
    assert "stock_quantity must be non-negative" in result["error_reason"]


def test_build_bigquery_row_matches_declared_schema() -> None:
    result_type, record = normalize_supplier_product(
        {
            "supplier_product_id": "SUP-001",
            "sku": "SKU-001",
            "product_name": "Cafe torrado",
            "category": "Bebidas",
            "brand": "Marca",
            "price": "12.50",
            "stock_quantity": "10",
            "source_updated_at": "2026-11-10T00:00:00Z",
        },
        source_system="supplier_csv",
        batch_id="batch-001",
        ingested_at="2026-11-10T12:00:00+00:00",
    )

    assert result_type == VALID_TAG
    row = build_bigquery_row(record)
    schema_names = {field["name"] for field in BIGQUERY_SCHEMA["fields"]}

    assert set(row) == schema_names
    assert row["price"] == "12.50"
    assert row["stock_quantity"] == 10


def test_beam_transform_separates_valid_and_invalid_records() -> None:
    lines = [
        "SUP-001,SKU-001,Produto 1,Bebidas,Marca,12.50,10,2026-11-10",
        "SUP-002,,Produto 2,Bebidas,Marca,abc,-1,2026-11-10",
    ]

    with BeamTestPipeline() as pipeline:
        outputs = (
            pipeline
            | beam.Create(lines)
            | beam.ParDo(
                NormalizeSupplierProduct(
                    source_system="supplier_csv",
                    batch_id="batch-001",
                    ingested_at="2026-11-10T12:00:00+00:00",
                )
            ).with_outputs(INVALID_TAG, main=VALID_TAG)
        )

        def assert_one(records: list[dict[str, object]]) -> None:
            assert len(records) == 1, records

        assert_that(outputs[VALID_TAG], assert_one, label="one valid")
        assert_that(outputs[INVALID_TAG], assert_one, label="one invalid")
