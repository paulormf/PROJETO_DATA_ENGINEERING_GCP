import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from ingestion.pubsub_probe import decode_cdc_message, summarize_event


def test_decode_cdc_message() -> None:
    payload = {
        "before": None,
        "after": {"armazem_id": 2},
        "source": {
            "schema": "ecommerce",
            "table": "armazens",
            "lsn": 6202068960,
            "txId": 904,
            "snapshot": True,
        },
        "op": "r",
    }

    event = decode_cdc_message(json.dumps(payload).encode("utf-8"))

    assert event.table == "armazens"
    assert event.operation == "r"
    assert event.is_snapshot is True


def test_summary_does_not_include_business_payload() -> None:
    payload = {
        "before": None,
        "after": {"armazem_id": 2, "nome_armazem": "Centro"},
        "source": {"schema": "ecommerce", "table": "armazens"},
        "op": "r",
    }
    event = decode_cdc_message(json.dumps(payload).encode("utf-8"))

    summary = summarize_event(
        event,
        message_id="message-1",
        ordering_key='{"armazem_id":2}',
    )

    assert summary["message_id"] == "message-1"
    assert summary["table"] == "armazens"
    assert "after" not in summary
    assert "nome_armazem" not in str(summary)


def test_decode_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="JSON UTF-8 válido"):
        decode_cdc_message(b"not-json")
