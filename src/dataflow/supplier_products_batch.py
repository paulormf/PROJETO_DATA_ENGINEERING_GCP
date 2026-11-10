"""Normaliza um CSV de fornecedor usando Apache Beam Batch.

O pipeline foi desenhado para rodar primeiro com DirectRunner e depois com
DataflowRunner. A entrada deve ser um CSV simples, com uma linha por produto,
e a saída é JSON Lines para facilitar a inspeção local antes da integração
com BigQueryIO.
"""

from __future__ import annotations

import csv
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

CSV_COLUMNS = (
    "supplier_product_id",
    "sku",
    "product_name",
    "category",
    "brand",
    "price",
    "stock_quantity",
    "source_updated_at",
)
REQUIRED_COLUMNS = (
    "supplier_product_id",
    "sku",
    "product_name",
    "category",
    "price",
    "stock_quantity",
)
VALID_TAG = "valid"
INVALID_TAG = "invalid"

BIGQUERY_SCHEMA = {
    "fields": [
        {"name": "source_system", "type": "STRING", "mode": "REQUIRED"},
        {"name": "batch_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "ingested_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "record_hash", "type": "STRING", "mode": "REQUIRED"},
        {"name": "supplier_product_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "sku", "type": "STRING", "mode": "REQUIRED"},
        {"name": "product_name", "type": "STRING", "mode": "REQUIRED"},
        {"name": "category", "type": "STRING", "mode": "REQUIRED"},
        {"name": "brand", "type": "STRING", "mode": "NULLABLE"},
        {"name": "price", "type": "NUMERIC", "mode": "REQUIRED"},
        {"name": "stock_quantity", "type": "INTEGER", "mode": "REQUIRED"},
        {"name": "source_updated_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ]
}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_csv_line(line: str) -> dict[str, str | None]:
    """Converte uma linha CSV em um registro com contrato conhecido."""
    if not line.strip():
        raise ValueError("linha vazia")

    values = next(csv.reader([line]))
    if len(values) > len(CSV_COLUMNS):
        raise ValueError("quantidade de colunas maior que o contrato")

    padded_values = values + [None] * (len(CSV_COLUMNS) - len(values))
    return dict(zip(CSV_COLUMNS, padded_values, strict=True))


def _record_hash(record: dict[str, Any]) -> str:
    canonical = json.dumps(
        {column: record.get(column) for column in CSV_COLUMNS},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_supplier_product(
    record: dict[str, Any],
    *,
    source_system: str,
    batch_id: str,
    ingested_at: str,
) -> tuple[Literal["valid", "invalid"], dict[str, Any]]:
    """Valida e normaliza um produto, preservando dinheiro como texto decimal."""
    normalized = {column: _clean(record.get(column)) for column in CSV_COLUMNS}
    errors: list[str] = []

    for column in REQUIRED_COLUMNS:
        if not normalized[column]:
            errors.append(f"{column} is required")

    price: Decimal | None = None
    if normalized["price"]:
        try:
            price = Decimal(normalized["price"])
            if not price.is_finite() or price < 0:
                errors.append("price must be a finite non-negative decimal")
        except InvalidOperation:
            errors.append("price must be a decimal")

    stock_quantity: int | None = None
    if normalized["stock_quantity"]:
        try:
            stock_quantity = int(normalized["stock_quantity"])
            if stock_quantity < 0:
                errors.append("stock_quantity must be non-negative")
        except ValueError:
            errors.append("stock_quantity must be an integer")

    if errors:
        return "invalid", {
            "source_system": source_system,
            "batch_id": batch_id,
            "ingested_at": ingested_at,
            "error_reason": "; ".join(errors),
            "raw_record": normalized,
        }

    valid_record = {
        "source_system": source_system,
        "batch_id": batch_id,
        "ingested_at": ingested_at,
        "record_hash": _record_hash(normalized),
        "supplier_product_id": normalized["supplier_product_id"],
        "sku": normalized["sku"],
        "product_name": normalized["product_name"],
        "category": normalized["category"],
        "brand": normalized["brand"] or None,
        "price": format(price, "f") if price is not None else None,
        "stock_quantity": stock_quantity,
        "source_updated_at": normalized["source_updated_at"] or None,
    }
    return "valid", valid_record


def build_bigquery_row(record: dict[str, Any]) -> dict[str, Any]:
    """Seleciona somente os campos do contrato de destino BigQuery."""
    return {
        field["name"]: record.get(field["name"])
        for field in BIGQUERY_SCHEMA["fields"]
    }


class NormalizeSupplierProduct(beam.DoFn):
    """Transforma linhas CSV em registros válidos ou eventos de DLQ."""

    def __init__(self, *, source_system: str, batch_id: str, ingested_at: str) -> None:
        self.source_system = source_system
        self.batch_id = batch_id
        self.ingested_at = ingested_at
        self.processed = Metrics.counter(self.__class__, "processed_records")
        self.valid = Metrics.counter(self.__class__, "valid_records")
        self.invalid = Metrics.counter(self.__class__, "invalid_records")

    def process(self, line: str) -> Any:
        self.processed.inc()
        try:
            record = parse_csv_line(line)
            result_type, payload = normalize_supplier_product(
                record,
                source_system=self.source_system,
                batch_id=self.batch_id,
                ingested_at=self.ingested_at,
            )
        except ValueError as exc:
            self.invalid.inc()
            yield TaggedOutput(
                INVALID_TAG,
                {
                    "source_system": self.source_system,
                    "batch_id": self.batch_id,
                    "ingested_at": self.ingested_at,
                    "error_reason": str(exc),
                    "raw_line": line,
                },
            )
            return

        if result_type == VALID_TAG:
            self.valid.inc()
            yield payload
        else:
            self.invalid.inc()
            yield TaggedOutput(INVALID_TAG, payload)


class _LegacySupplierProductsOptions:
    """Argumentos específicos do pipeline, além dos argumentos Beam padrão."""

    @classmethod
    def _add_argparse_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--input", help="CSV local ou URI gs://")
        parser.add_argument("--output", help="Prefixo JSONL válido")
        parser.add_argument(
            "--dead-letter-output",
            "--dead_letter_output",
            dest="dead_letter_output",
            help="Prefixo JSONL de rejeitos",
        )
        parser.add_argument(
            "--bigquery-table",
            "--bigquery_table",
            dest="bigquery_table",
            help="Tabela BigQuery completa: projeto:dataset.tabela",
        )
        parser.add_argument(
            "--source-system",
            "--source_system",
            dest="source_system",
            default="supplier_csv",
        )
        parser.add_argument("--batch-id", "--batch_id", dest="batch_id")
        parser.add_argument(
            "--ingested-at", "--ingested_at", dest="ingested_at"
        )


SupplierProductsOptions = BatchPipelineOptions


def run(pipeline_args: list[str] | None = None) -> None:
    options = SupplierProductsOptions(pipeline_args)
    required_options = {
        "input": options.input,
        "dead_letter_output": options.dead_letter_output,
        "batch_id": options.batch_id,
    }
    missing_options = [name for name, value in required_options.items() if not value]
    if missing_options:
        raise ValueError(
            "argumentos obrigatorios ausentes: "
            + ", ".join(f"--{name.replace('_', '-')}" for name in missing_options)
        )
    if not options.output and not options.bigquery_table:
        raise ValueError("informe --output ou --bigquery-table")
    google_options = options.view_as(GoogleCloudOptions)
    if options.bigquery_table and not google_options.temp_location:
        raise ValueError(
            "--temp_location deve ser informado quando --bigquery-table for usado"
        )
    ingested_at = options.ingested_at or datetime.now(UTC).isoformat()
    if not options.batch_id.strip():
        raise ValueError("batch_id deve ser informado")
    source_system = options.source_system or "supplier_csv"
    if not source_system.strip():
        raise ValueError("source_system deve ser informado")

    with beam.Pipeline(options=options) as pipeline:
        results = (
            pipeline
            | "Read supplier CSV" >> beam.io.ReadFromText(options.input, skip_header_lines=1)
            | "Normalize and validate" >> beam.ParDo(
                NormalizeSupplierProduct(
                    source_system=source_system,
                    batch_id=options.batch_id,
                    ingested_at=ingested_at,
                )
            ).with_outputs(INVALID_TAG, main=VALID_TAG)
        )

        if options.output:
            (
                results[VALID_TAG]
                | "Serialize valid JSONL" >> beam.Map(json.dumps)
                | "Write valid JSONL"
                >> beam.io.WriteToText(
                    options.output,
                    file_name_suffix=".jsonl",
                    shard_name_template="-SS-of-NN",
                )
            )
        (
            results[INVALID_TAG]
            | "Serialize dead letter JSONL" >> beam.Map(json.dumps)
            | "Write dead letter JSONL"
            >> beam.io.WriteToText(
                options.dead_letter_output,
                file_name_suffix=".jsonl",
                shard_name_template="-SS-of-NN",
            )
        )
        if options.bigquery_table:
            (
                results[VALID_TAG]
                | "Prepare BigQuery rows" >> beam.Map(build_bigquery_row)
                | "Write valid rows to BigQuery"
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
