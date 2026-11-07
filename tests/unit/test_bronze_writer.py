import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from ingestion.bronze_writer import LocalBronzeWriter, event_id_for
from ingestion.cdc_contract import parse_cdc_event


def build_event() -> object:
    return parse_cdc_event(
        {
            "before": None,
            "after": {"armazem_id": 2, "nome_armazem": "Centro"},
            "source": {
                "schema": "ecommerce",
                "table": "armazens",
                "lsn": 6202068960,
                "txId": 904,
                "snapshot": True,
            },
            "op": "r",
        }
    )


def test_event_id_is_deterministic() -> None:
    event = build_event()

    assert event_id_for(event) == event_id_for(event)
    assert len(event_id_for(event)) == 64


def test_writer_is_idempotent_for_same_event(tmp_path: Path) -> None:
    writer = LocalBronzeWriter(tmp_path)
    event = build_event()
    timestamp = datetime(2026, 11, 7, tzinfo=timezone.utc)

    assert writer.write(event, ingested_at=timestamp) is True
    assert writer.write(event, ingested_at=timestamp) is False

    output_path = tmp_path / "raw" / "table=armazens" / "events.jsonl"
    records = [json.loads(line) for line in output_path.read_text().splitlines()]

    assert len(records) == 1
    assert records[0]["event_id"] == event_id_for(event)
    assert records[0]["raw"]["after"]["armazem_id"] == 2
