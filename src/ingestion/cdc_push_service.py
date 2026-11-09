"""Endpoint Cloud Run para receber envelopes CDC via Pub/Sub push."""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime
import json
import os
from typing import Any, Protocol

from flask import Flask, jsonify, request

from ingestion.bronze_writer import event_id_for
from ingestion.cdc_contract import CdcContractError, CdcEvent
from ingestion.pubsub_probe import decode_cdc_message


class CdcPushError(ValueError):
    """Indica que o envelope recebido pelo endpoint nao atende ao contrato."""


class CdcRecordWriter(Protocol):
    """Backend minimo usado pelo handler HTTP e pelos testes locais."""

    def write(self, record: dict[str, Any]) -> None:
        """Persiste um registro Bronze ou levanta uma excecao recuperavel."""


def _canonical_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode_message_data(value: Any) -> bytes:
    if not isinstance(value, str) or not value:
        raise CdcPushError("message.data precisa ser Base64 nao vazio")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CdcPushError("message.data nao e Base64 valido") from exc


def _message_metadata(message: dict[str, Any]) -> tuple[str, str]:
    message_id = message.get("messageId")
    ordering_key = message.get("orderingKey", "")
    if not isinstance(message_id, str) or not message_id:
        raise CdcPushError("message.messageId e obrigatorio")
    if not isinstance(ordering_key, str):
        raise CdcPushError("message.orderingKey precisa ser texto")
    return message_id, ordering_key


def build_bronze_record(
    push_payload: Any,
    *,
    ingested_at: datetime | None = None,
) -> dict[str, Any]:
    """Converte o envelope Pub/Sub push em um registro CDC Bronze.

    O payload Debezium permanece preservado em ``raw_json``. Os campos
    ``before_json`` e ``after_json`` ficam serializados como texto JSON para
    manter o contrato independente da criacao previa de um schema BigQuery.
    """

    if not isinstance(push_payload, dict):
        raise CdcPushError("o corpo Pub/Sub precisa ser um objeto JSON")

    message = push_payload.get("message")
    if not isinstance(message, dict):
        raise CdcPushError("message e obrigatorio e precisa ser um objeto")

    message_id, ordering_key = _message_metadata(message)
    try:
        event: CdcEvent = decode_cdc_message(_decode_message_data(message.get("data")))
    except (CdcContractError, ValueError) as exc:
        raise CdcPushError(str(exc)) from exc

    received_at = ingested_at or datetime.now(UTC)
    if received_at.tzinfo is None:
        raise ValueError("ingested_at precisa conter timezone")

    return {
        "event_id": event_id_for(event),
        "pubsub_message_id": message_id,
        "ordering_key": ordering_key,
        "source_schema": event.schema,
        "source_table": event.table,
        "operation": event.operation,
        "snapshot": event.snapshot,
        "source_lsn": event.source_lsn,
        "transaction_id": event.transaction_id,
        "before_json": _canonical_json(event.before),
        "after_json": _canonical_json(event.after),
        "raw_json": _canonical_json(event.raw),
        "ingested_at": received_at.astimezone(UTC).isoformat(),
    }


class BigQueryCdcWriter:
    """Writer inicial para a tabela raw CDC do BigQuery.

    ``event_id`` e enviado como ``insertId`` para reduzir duplicidades em
    reentregas. A deduplicacao definitiva continuara sendo feita no modelo
    Silver, pois a deduplicacao de streaming do BigQuery e best effort.
    """

    def __init__(self, *, client: Any, table_id: str) -> None:
        self.client = client
        self.table_id = table_id

    @classmethod
    def from_environment(cls) -> "BigQueryCdcWriter":
        from google.cloud import bigquery

        table_id = os.getenv("BQ_CDC_TABLE")
        if not table_id:
            raise RuntimeError("BQ_CDC_TABLE nao foi configurada")
        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        return cls(client=bigquery.Client(project=project_id), table_id=table_id)

    def write(self, record: dict[str, Any]) -> None:
        errors = self.client.insert_rows_json(
            self.table_id,
            [record],
            row_ids=[record["event_id"]],
            skip_invalid_rows=False,
            ignore_unknown_values=False,
        )
        if errors:
            raise RuntimeError(f"BigQuery rejeitou o evento CDC: {errors}")


def create_app(writer: CdcRecordWriter | None = None) -> Flask:
    """Cria a aplicacao Flask com writer injetavel para testes."""

    app = Flask(__name__)

    @app.get("/healthz")
    def healthz() -> tuple[Any, int]:
        return jsonify({"status": "ok"}), 200

    @app.post("/pubsub")
    def receive_pubsub() -> tuple[Any, int]:
        push_payload = request.get_json(silent=True)
        try:
            record = build_bronze_record(push_payload)
        except CdcPushError as exc:
            app.logger.warning("Mensagem CDC invalida: %s", exc)
            return jsonify({"error": "invalid_cdc_message"}), 400

        active_writer = writer or BigQueryCdcWriter.from_environment()
        try:
            active_writer.write(record)
        except Exception:
            app.logger.exception("Falha ao persistir evento CDC")
            return jsonify({"error": "cdc_persistence_failed"}), 500

        return jsonify({"status": "persisted", "event_id": record["event_id"]}), 200

    return app


app = create_app()
