from __future__ import annotations

import json

import pytest

from dataflow.pubsub_streaming_shadow import (
    INVALID_TAG,
    VALID_TAG,
    BIGQUERY_SCHEMA,
    StreamingPipelineOptions,
    build_bigquery_row,
    normalize_stream_event,
)


def valid_event() -> dict[str, object]:
    return {
        "event_id": "evt-001",
        "event_type": "product_viewed",
        "event_time": "2026-11-10T20:00:00Z",
        "product_id": 10,
        "quantity": 1,
        "price": "12.50",
    }


def test_normalize_stream_event_preserves_event_time_and_payload() -> None:
    result_type, result = normalize_stream_event(
        json.dumps(valid_event()).encode(),
        source_system="synthetic_streaming_lab",
        received_at="2026-11-10T20:00:01+00:00",
    )

    assert result_type == VALID_TAG
    assert result["event_id"] == "evt-001"
    assert result["event_time"] == "2026-11-10T20:00:00+00:00"
    assert result["price"] == "12.50"
    assert result["received_at"] == "2026-11-10T20:00:01+00:00"
    assert json.loads(result["payload_json"]) == valid_event()


@pytest.mark.parametrize(
    "invalid_change",
    [
        {"event_id": ""},
        {"event_type": ""},
        {"event_time": "not-a-timestamp"},
        {"product_id": 0},
        {"quantity": -1},
        {"price": -1},
    ],
)
def test_normalize_stream_event_rejects_invalid_contract(
    invalid_change: dict[str, object],
) -> None:
    event = valid_event()
    event.update(invalid_change)

    result_type, result = normalize_stream_event(
        json.dumps(event),
        source_system="synthetic_streaming_lab",
    )

    assert result_type == INVALID_TAG
    assert result["error_reason"]


def test_build_bigquery_row_matches_declared_schema() -> None:
    result_type, record = normalize_stream_event(
        json.dumps(valid_event()),
        source_system="synthetic_streaming_lab",
    )

    assert result_type == VALID_TAG
    row = build_bigquery_row(record)
    schema_names = {field["name"] for field in BIGQUERY_SCHEMA["fields"]}

    assert set(row) == schema_names
    assert "_event_epoch" not in row


def test_streaming_template_options_accept_runtime_parameters() -> None:
    options = StreamingPipelineOptions(
        [
            "--input_subscription",
            "projects/p/subscriptions/events",
            "--output_table",
            "p:d.table",
            "--dead_letter_topic",
            "projects/p/topics/events-dlq",
            "--window_size_seconds",
            "60",
        ]
    )

    assert options.input_subscription.endswith("/events")
    assert options.output_table == "p:d.table"
    assert options.dead_letter_topic.endswith("events-dlq")
    assert options.window_size_seconds == 60
