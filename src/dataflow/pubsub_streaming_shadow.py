"""Processa eventos Pub/Sub em uma tabela BigQuery de sombra.

Este pipeline existe para praticar Apache Beam Streaming sem competir com o
consumidor Debezium de producao. Ele e somente um artefato versionado: nao
cria topico, assinatura ou job Dataflow automaticamente.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.pvalue import TaggedOutput
from apache_beam.transforms.window import FixedWindows, TimestampedValue

VALID_TAG = "valid"
INVALID_TAG = "invalid"

BIGQUERY_SCHEMA = {
    "fields": [
        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "source_system", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_type", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_time", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "received_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "product_id", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "quantity", "type": "INTEGER", "mode": "NULLABLE"},
        {"name": "price", "type": "NUMERIC", "mode": "NULLABLE"},
        {"name": "payload_json", "type": "STRING", "mode": "REQUIRED"},
    ]
}


class StreamingPipelineOptions(PipelineOptions):
    """Argumentos especificos do laboratorio Streaming."""

    @classmethod
    def _add_argparse_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--input-subscription",
            "--input_subscription",
            dest="input_subscription",
            help="Nome completo da assinatura Pub/Sub.",
        )
        parser.add_argument(
            "--output-table",
            "--output_table",
            dest="output_table",
            help="Tabela BigQuery no formato projeto:dataset.tabela.",
        )
        parser.add_argument(
            "--dead-letter-topic",
            "--dead_letter_topic",
            dest="dead_letter_topic",
            help="Nome completo do topico Pub/Sub para rejeitos.",
        )
        # BatchPipelineOptions uses the same logical option. Beam may collect
        # both option classes in one process during tests, so do not register
        # a duplicate argparse flag when it already exists.
        if not any(
            flag in getattr(parser, "_option_string_actions", {})
            for flag in ("--source-system", "--source_system")
        ):
            parser.add_argument(
                "--source-system",
                "--source_system",
                dest="source_system",
                default="synthetic_streaming_lab",
            )
        parser.add_argument(
            "--window-size-seconds",
            "--window_size_seconds",
            dest="window_size_seconds",
            type=int,
            default=60,
        )
        parser.add_argument(
            "--allowed-lateness-seconds",
            "--allowed_lateness_seconds",
            dest="allowed_lateness_seconds",
            type=int,
            default=120,
        )
        parser.add_argument(
            "--triggering-frequency-seconds",
            "--triggering_frequency_seconds",
            dest="triggering_frequency_seconds",
            type=int,
            default=30,
        )


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _decimal_text(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return format(result, "f") if result.is_finite() else None


def _timestamp(value: Any) -> tuple[str | None, float | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None, None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    parsed = parsed.astimezone(UTC)
    return parsed.isoformat(), parsed.timestamp()


def normalize_stream_event(
    payload: str | bytes,
    *,
    source_system: str,
    received_at: str | None = None,
    attributes: dict[str, str] | None = None,
) -> tuple[Literal["valid", "invalid"], dict[str, Any]]:
    """Valida e normaliza um evento sintetico para o contrato de sombra."""

    raw_text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    try:
        document = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError) as exc:
        return INVALID_TAG, {
            "error_reason": "payload must be valid JSON",
            "raw_payload": raw_text,
        }

    if not isinstance(document, dict):
        return INVALID_TAG, {
            "error_reason": "payload must be a JSON object",
            "raw_payload": document,
        }

    event_id = _text(document.get("event_id") or document.get("id"))
    event_type = _text(document.get("event_type") or document.get("type"))
    event_time, event_epoch = _timestamp(document.get("event_time"))
    product_id = _integer(document.get("product_id"))
    quantity = _integer(document.get("quantity"))
    price = _decimal_text(document.get("price"))

    errors: list[str] = []
    if not event_id:
        errors.append("event_id is required")
    if not event_type:
        errors.append("event_type is required")
    if event_time is None:
        errors.append("event_time must be an ISO-8601 timestamp")
    if document.get("product_id") is not None and (product_id is None or product_id <= 0):
        errors.append("product_id must be a positive integer")
    if document.get("quantity") is not None and (quantity is None or quantity < 0):
        errors.append("quantity must be a non-negative integer")
    if document.get("price") is not None and (price is None or Decimal(price) < 0):
        errors.append("price must be a non-negative decimal")

    if errors:
        return INVALID_TAG, {
            "error_reason": "; ".join(errors),
            "source_system": source_system,
            "attributes": attributes or {},
            "raw_payload": document,
        }

    received = received_at or datetime.now(UTC).isoformat()
    return VALID_TAG, {
        "event_id": event_id,
        "source_system": source_system,
        "event_type": event_type,
        "event_time": event_time,
        "received_at": received,
        "product_id": product_id,
        "quantity": quantity,
        "price": price,
        "payload_json": json.dumps(document, ensure_ascii=False, sort_keys=True),
        "_event_epoch": event_epoch,
    }


def build_bigquery_row(record: dict[str, Any]) -> dict[str, Any]:
    """Remove o campo interno usado apenas para event-time no Beam."""

    return {
        field["name"]: record.get(field["name"])
        for field in BIGQUERY_SCHEMA["fields"]
    }


class NormalizePubSubEvent(beam.DoFn):
    """Transforma PubsubMessage em registros validos ou rejeitos."""

    def __init__(self, *, source_system: str) -> None:
        self.source_system = source_system

    def process(self, message: Any) -> Any:
        attributes = dict(getattr(message, "attributes", {}) or {})
        payload = getattr(message, "data", message)
        result_type, record = normalize_stream_event(
            payload,
            source_system=self.source_system,
            attributes=attributes,
        )
        if result_type == VALID_TAG:
            event_epoch = record.pop("_event_epoch")
            yield TimestampedValue(record, event_epoch)
        else:
            yield TaggedOutput(INVALID_TAG, record)


def _first_record(records: Any) -> dict[str, Any]:
    """Mantem um evento por chave dentro da janela de event-time."""

    return next(iter(records))


def run(pipeline_args: list[str] | None = None) -> None:
    options = StreamingPipelineOptions(pipeline_args)
    required = {
        "input-subscription": options.input_subscription,
        "output-table": options.output_table,
        "dead-letter-topic": options.dead_letter_topic,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("argumentos ausentes: " + ", ".join(missing))
    if options.window_size_seconds <= 0 or options.allowed_lateness_seconds < 0:
        raise ValueError("janela e lateness devem ser valores validos")
    if options.triggering_frequency_seconds <= 0:
        raise ValueError("triggering_frequency_seconds deve ser positivo")

    source_system = options.source_system or "synthetic_streaming_lab"
    standard_options = options.view_as(StandardOptions)
    standard_options.streaming = True

    with beam.Pipeline(options=options) as pipeline:
        parsed = (
            pipeline
            | "Read PubSub events"
            >> beam.io.ReadFromPubSub(
                subscription=options.input_subscription,
                with_attributes=True,
            )
            | "Normalize and validate events"
            >> beam.ParDo(
                NormalizePubSubEvent(source_system=source_system)
            ).with_outputs(INVALID_TAG, main=VALID_TAG)
        )

        (
            parsed[INVALID_TAG]
            | "Serialize streaming DLQ"
            >> beam.Map(lambda row: json.dumps(row, ensure_ascii=False))
            | "Write streaming DLQ"
            >> beam.io.WriteToPubSub(topic=options.dead_letter_topic)
        )

        deduplicated = (
            parsed[VALID_TAG]
            | "Window by event time"
            >> beam.WindowInto(
                FixedWindows(options.window_size_seconds),
                allowed_lateness=options.allowed_lateness_seconds,
            )
            | "Key by event id"
            >> beam.Map(lambda row: (row["event_id"], row))
            | "Deduplicate event ids"
            >> beam.CombinePerKey(_first_record)
            | "Drop event id key"
            >> beam.Values()
            | "Prepare BigQuery rows"
            >> beam.Map(build_bigquery_row)
        )

        deduplicated | "Write streaming shadow table" >> beam.io.WriteToBigQuery(
            options.output_table,
            schema=BIGQUERY_SCHEMA,
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            method=beam.io.WriteToBigQuery.Method.STREAMING_INSERTS,
            triggering_frequency=options.triggering_frequency_seconds,
        )


if __name__ == "__main__":
    run()
