import base64
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from ingestion.bronze_writer import event_id_for
from ingestion.cdc_push_service import (
    CdcPushError,
    build_bronze_record,
    create_app,
)
from ingestion.cdc_contract import parse_cdc_event


def build_push_payload() -> tuple[dict[str, object], dict[str, object]]:
    debezium_payload: dict[str, object] = {
        "before": None,
        "after": {"armazem_id": 2, "nome_armazem": "Centro"},
        "source": {
            "schema": "ecommerce",
            "table": "armazens",
            "lsn": 6202068960,
            "txId": 904,
            "snapshot": False,
        },
        "op": "u",
    }
    encoded = base64.b64encode(
        json.dumps(debezium_payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return (
        {
            "message": {
                "data": encoded,
                "messageId": "message-123",
                "orderingKey": '{"armazem_id":2}',
            },
            "subscription": "projects/test/subscriptions/ecommerce-gcp-v2-armazens-sub",
        },
        debezium_payload,
    )


def test_build_bronze_record_preserves_event_and_metadata() -> None:
    push_payload, debezium_payload = build_push_payload()
    event = parse_cdc_event(debezium_payload)

    record = build_bronze_record(
        push_payload,
        ingested_at=datetime(2026, 11, 9, 18, 0, tzinfo=UTC),
    )

    assert record["event_id"] == event_id_for(event)
    assert record["source_table"] == "armazens"
    assert record["operation"] == "u"
    assert record["source_lsn"] == 6202068960
    assert record["ingested_at"] == "2026-11-09T18:00:00+00:00"
    assert json.loads(record["raw_json"]) == debezium_payload


def test_build_bronze_record_rejects_invalid_push_envelope() -> None:
    with pytest.raises(CdcPushError, match="message e obrigatorio"):
        build_bronze_record({})


class FakeWriter:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def write(self, record: dict[str, object]) -> None:
        self.records.append(record)


def test_http_endpoint_persists_valid_message() -> None:
    push_payload, _ = build_push_payload()
    writer = FakeWriter()
    client = create_app(writer).test_client()

    response = client.post("/pubsub", json=push_payload)

    assert response.status_code == 200
    assert response.json["status"] == "persisted"
    assert len(writer.records) == 1


def test_http_endpoint_returns_400_for_invalid_message() -> None:
    client = create_app(FakeWriter()).test_client()

    response = client.post("/pubsub", json={})

    assert response.status_code == 400
    assert response.json == {"error": "invalid_cdc_message"}


def test_health_endpoint_does_not_require_bigquery() -> None:
    client = create_app().test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}
