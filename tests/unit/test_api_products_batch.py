from __future__ import annotations

import json

import apache_beam as beam
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.testing.test_pipeline import TestPipeline as BeamTestPipeline
from apache_beam.testing.util import assert_that

from dataflow.api_products_batch import (
    BIGQUERY_SCHEMA,
    INVALID_TAG,
    VALID_TAG,
    ApiProductsOptions,
    NormalizeDummyJsonProducts,
    build_bigquery_row,
    normalize_dummyjson_product,
    parse_raw_envelope,
)


def valid_product() -> dict[str, object]:
    return {
        "id": 1,
        "title": "Produto API",
        "description": "Descricao",
        "category": "beauty",
        "price": 9.99,
        "discountPercentage": 10.5,
        "rating": 4.5,
        "stock": 20,
        "tags": ["beauty"],
        "brand": "Marca",
        "sku": "SKU-001",
        "weight": 4,
        "availabilityStatus": "In Stock",
        "minimumOrderQuantity": 1,
        "meta": {
            "createdAt": "2025-01-01T00:00:00.000Z",
            "updatedAt": "2026-01-01T00:00:00.000Z",
        },
        "images": ["https://example.test/image.webp"],
        "thumbnail": "https://example.test/thumb.webp",
    }


def envelope(*products: dict[str, object]) -> str:
    return json.dumps(
        {
            "source_system": "dummyjson_products_api",
            "extracted_at": "2026-11-10T17:00:00+00:00",
            "products": list(products),
        }
    )


def test_parse_raw_envelope_returns_products_and_extraction_timestamp() -> None:
    products, extracted_at = parse_raw_envelope(envelope(valid_product()))

    assert products == [valid_product()]
    assert extracted_at == "2026-11-10T17:00:00+00:00"


def test_normalize_dummyjson_product_flattens_contract() -> None:
    result_type, result = normalize_dummyjson_product(
        valid_product(),
        source_system="dummyjson_products_api",
        batch_id="api-001",
        ingested_at="2026-11-10T17:01:00+00:00",
        source_extracted_at="2026-11-10T17:00:00+00:00",
    )

    assert result_type == VALID_TAG
    assert result["product_id"] == 1
    assert result["price"] == "9.99"
    assert result["stock"] == 20
    assert json.loads(result["tags_json"]) == ["beauty"]
    assert len(result["record_hash"]) == 64


def test_normalize_dummyjson_product_sends_invalid_record_to_dlq_contract() -> None:
    invalid = valid_product()
    invalid.update({"title": "", "price": "abc", "stock": -1, "rating": 6})

    result_type, result = normalize_dummyjson_product(
        invalid,
        source_system="dummyjson_products_api",
        batch_id="api-001",
        ingested_at="2026-11-10T17:01:00+00:00",
        source_extracted_at="2026-11-10T17:00:00+00:00",
    )

    assert result_type == INVALID_TAG
    assert "title is required" in result["error_reason"]
    assert "price must be" in result["error_reason"]
    assert "stock must be" in result["error_reason"]
    assert "rating must be" in result["error_reason"]


def test_beam_transform_separates_valid_and_invalid_products() -> None:
    invalid = valid_product()
    invalid["price"] = "abc"

    with BeamTestPipeline() as pipeline:
        outputs = (
            pipeline
            | beam.Create([envelope(valid_product(), invalid)])
            | beam.ParDo(
                NormalizeDummyJsonProducts(
                    source_system="dummyjson_products_api",
                    batch_id="api-001",
                    ingested_at="2026-11-10T17:01:00+00:00",
                )
            ).with_outputs(INVALID_TAG, main=VALID_TAG)
        )

        def assert_valid(records: list[dict[str, object]]) -> None:
            assert len(records) == 1, records
            assert records[0]["product_id"] == 1
            assert len(records[0]["record_hash"]) == 64

        def assert_invalid(records: list[dict[str, object]]) -> None:
            assert len(records) == 1, records
            assert "price must be" in records[0]["error_reason"]

        assert_that(outputs[VALID_TAG], assert_valid, label="one valid")
        assert_that(outputs[INVALID_TAG], assert_invalid, label="one invalid")
