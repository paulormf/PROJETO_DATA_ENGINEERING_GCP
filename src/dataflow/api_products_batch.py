"""Normaliza o envelope Raw de produtos DummyJSON com Apache Beam Batch."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import apache_beam as beam
from apache_beam.metrics.metric import Metrics
from apache_beam.options.pipeline_options import GoogleCloudOptions
from apache_beam.pvalue import TaggedOutput

from dataflow.common_options import BatchPipelineOptions

VALID_TAG = "valid"
INVALID_TAG = "invalid"
MAX_RAW_DOCUMENT_IN_DLQ = 10_000

BIGQUERY_SCHEMA = {
    "fields": [
        {"name": "source_system", "type": "STRING", "mode": "REQUIRED"},
        {"name": "batch_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "ingested_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "source_extracted_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "record_hash", "type": "STRING", "mode": "REQUIRED"},
        {"name": "product_id", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "title", "type": "STRING", "mode": "REQUIRED"},
        {"name": "description", "type": "STRING", "mode": "NULLABLE"},
        {"name": "category", "type": "STRING", "mode": "REQUIRED"},
        {"name": "price", "type": "NUMERIC", "mode": "REQUIRED"},
        {"name": "discount_percentage", "type": "NUMERIC", "mode": "NULLABLE"},
        {"name": "rating", "type": "NUMERIC", "mode": "NULLABLE"},
        {"name": "stock", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "brand", "type": "STRING", "mode": "NULLABLE"},
        {"name": "sku", "type": "STRING", "mode": "NULLABLE"},
        {"name": "weight", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "availability_status", "type": "STRING", "mode": "NULLABLE"},
        {"name": "minimum_order_quantity", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "source_created_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
        {"name": "source_updated_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
        {"name": "tags_json", "type": "STRING", "mode": "NULLABLE"},
        {"name": "images_json", "type": "STRING", "mode": "NULLABLE"},
        {"name": "thumbnail", "type": "STRING", "mode": "NULLABLE"},
    ]
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _timestamp(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return value.strip()


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None


def _record_hash(product: dict[str, Any]) -> str:
    canonical = json.dumps(
        product,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_dummyjson_product(
    product: dict[str, Any],
    *,
    source_system: str,
    batch_id: str,
    ingested_at: str,
    source_extracted_at: str,
) -> tuple[Literal["valid", "invalid"], dict[str, Any]]:
    """Valida e achata um produto DummyJSON para o contrato Bronze."""
    errors: list[str] = []

    product_id = _integer(product.get("id"))
    if product_id is None or product_id <= 0:
        errors.append("id must be a positive integer")

    title = _text(product.get("title"))
    if not title:
        errors.append("title is required")

    category = _text(product.get("category"))
    if not category:
        errors.append("category is required")

    price = _decimal(product.get("price"))
    if price is None or price < 0:
        errors.append("price must be a finite non-negative decimal")

    stock = _integer(product.get("stock"))
    if stock is None or stock < 0:
        errors.append("stock must be a non-negative integer")

    discount_percentage = _decimal(product.get("discountPercentage"))
    if discount_percentage is not None and discount_percentage < 0:
        errors.append("discountPercentage must be non-negative")

    rating = _decimal(product.get("rating"))
    if rating is not None and (rating < 0 or rating > 5):
        errors.append("rating must be between 0 and 5")

    tags = product.get("tags")
    if tags is not None and not isinstance(tags, list):
        errors.append("tags must be a list")

    meta = product.get("meta")
    if meta is not None and not isinstance(meta, dict):
        errors.append("meta must be an object")
    meta = meta if isinstance(meta, dict) else {}

    if errors:
        return "invalid", {
            "source_system": source_system,
            "batch_id": batch_id,
            "ingested_at": ingested_at,
            "error_reason": "; ".join(errors),
            "raw_record": product,
        }

    valid_record = {
        "source_system": source_system,
        "batch_id": batch_id,
        "ingested_at": ingested_at,
        "source_extracted_at": source_extracted_at,
        "record_hash": _record_hash(product),
        "product_id": product_id,
        "title": title,
        "description": _text(product.get("description")) or None,
        "category": category,
        "price": format(price, "f"),
        "discount_percentage": (
            format(discount_percentage, "f") if discount_percentage is not None else None
        ),
        "rating": format(rating, "f") if rating is not None else None,
        "stock": stock,
        "brand": _text(product.get("brand")) or None,
        "sku": _text(product.get("sku")) or None,
        "weight": _integer(product.get("weight")),
        "availability_status": _text(product.get("availabilityStatus")) or None,
        "minimum_order_quantity": _integer(product.get("minimumOrderQuantity")),
        "source_created_at": _timestamp(meta.get("createdAt")),
        "source_updated_at": _timestamp(meta.get("updatedAt")),
        "tags_json": _json_text(tags),
        "images_json": _json_text(product.get("images")),
        "thumbnail": _text(product.get("thumbnail")) or None,
    }
    return "valid", valid_record


def parse_raw_envelope(document: str) -> tuple[list[dict[str, Any]], str]:
    """Valida o envelope e retorna produtos e timestamp da extração."""
    try:
        payload = json.loads(document)
    except json.JSONDecodeError as exc:
        raise ValueError("raw input is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("raw input must be a JSON object")
    products = payload.get("products")
    extracted_at = _timestamp(payload.get("extracted_at"))
    if not isinstance(products, list):
        raise ValueError("raw envelope must contain products as a list")
    if extracted_at is None:
        raise ValueError("raw envelope must contain a valid extracted_at")
    if not all(isinstance(product, dict) for product in products):
        raise ValueError("products must contain only JSON objects")
    return products, extracted_at


def build_bigquery_row(record: dict[str, Any]) -> dict[str, Any]:
    """Seleciona apenas os campos declarados no schema BigQuery."""
    return {
        field["name"]: record.get(field["name"])
        for field in BIGQUERY_SCHEMA["fields"]
    }


class NormalizeDummyJsonProducts(beam.DoFn):
    """Transforma o envelope Raw em registros validos ou eventos de DLQ."""

    def __init__(self, *, source_system: str, batch_id: str, ingested_at: str) -> None:
        self.source_system = source_system
        self.batch_id = batch_id
        self.ingested_at = ingested_at
        self.processed = Metrics.counter(self.__class__, "processed_records")
        self.valid = Metrics.counter(self.__class__, "valid_records")
        self.invalid = Metrics.counter(self.__class__, "invalid_records")

    def process(self, document: str) -> Any:
        try:
            products, source_extracted_at = parse_raw_envelope(document)
            for product in products:
                self.processed.inc()
                result_type, payload = normalize_dummyjson_product(
                    product,
                    source_system=self.source_system,
                    batch_id=self.batch_id,
                    ingested_at=self.ingested_at,
                    source_extracted_at=source_extracted_at,
                )
                if result_type == VALID_TAG:
                    self.valid.inc()
                    yield payload
                else:
                    self.invalid.inc()
                    yield TaggedOutput(INVALID_TAG, payload)
        except ValueError as exc:
            self.invalid.inc()
            yield TaggedOutput(
                INVALID_TAG,
                {
                    "source_system": self.source_system,
                    "batch_id": self.batch_id,
                    "ingested_at": self.ingested_at,
                    "error_reason": str(exc),
                    "raw_document": document[:MAX_RAW_DOCUMENT_IN_DLQ],
                },
            )


ApiProductsOptions = BatchPipelineOptions


def run(pipeline_args: list[str] | None = None) -> None:
    options = ApiProductsOptions(pipeline_args)
    required_options = {
        "input": options.input,
        "dead_letter_output": options.dead_letter_output,
        "batch_id": options.batch_id,
    }
    missing_options = [name for name, value in required_options.items() if not value]
    if missing_options:
        raise ValueError(
            "required arguments missing: "
            + ", ".join(f"--{name.replace('_', '-')}" for name in missing_options)
        )
    if not options.output and not options.bigquery_table:
        raise ValueError("provide --output or --bigquery-table")
    google_options = options.view_as(GoogleCloudOptions)
    if options.bigquery_table and not google_options.temp_location:
        raise ValueError("--temp_location is required with --bigquery-table")
    ingested_at = options.ingested_at or datetime.now(UTC).isoformat()
    if not options.batch_id.strip():
        raise ValueError("batch_id must be provided")
    source_system = options.source_system or "dummyjson_products_api"
    if not source_system.strip():
        raise ValueError("source_system must be provided")

    with beam.Pipeline(options=options) as pipeline:
        results = (
            pipeline
            | "Read Raw JSON" >> beam.io.ReadFromText(options.input)
            | "Combine Raw JSON document" >> beam.CombineGlobally(lambda lines: "\n".join(lines))
            | "Normalize and validate API products" >> beam.ParDo(
                NormalizeDummyJsonProducts(
                    source_system=source_system,
                    batch_id=options.batch_id,
                    ingested_at=ingested_at,
                )
            ).with_outputs(INVALID_TAG, main=VALID_TAG)
        )

        if options.output:
            (
                results[VALID_TAG]
                | "Serialize valid API JSONL" >> beam.Map(json.dumps)
                | "Write valid API JSONL"
                >> beam.io.WriteToText(
                    options.output,
                    file_name_suffix=".jsonl",
                    shard_name_template="-SS-of-NN",
                )
            )
        (
            results[INVALID_TAG]
            | "Serialize API dead letter JSONL" >> beam.Map(json.dumps)
            | "Write API dead letter JSONL"
            >> beam.io.WriteToText(
                options.dead_letter_output,
                file_name_suffix=".jsonl",
                shard_name_template="-SS-of-NN",
            )
        )
        if options.bigquery_table:
            (
                results[VALID_TAG]
                | "Prepare API BigQuery rows" >> beam.Map(build_bigquery_row)
                | "Write API rows to BigQuery"
                >> beam.io.WriteToBigQuery(
                    options.bigquery_table,
                    schema=BIGQUERY_SCHEMA,
                    create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                    write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
                    method=beam.io.WriteToBigQuery.Method.FILE_LOADS,
                    custom_gcs_temp_location=google_options.temp_location,
                )
            )


if __name__ == "__main__":
    run()
