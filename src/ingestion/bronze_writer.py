"""Writer local de laboratório para validar a persistência Bronze."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingestion.cdc_contract import CdcEvent


def event_id_for(event: CdcEvent) -> str:
    """Gera um identificador determinístico para o envelope recebido."""

    canonical_payload = json.dumps(
        event.raw,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical_payload).hexdigest()


class LocalBronzeWriter:
    """Persiste eventos em JSONL e controla reprocessamento com SQLite.

    Este componente serve para validação local. A implementação cloud deverá
    usar armazenamento durável GCP e uma estratégia transacional apropriada.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.ledger_path = root / "state" / "bronze_ledger.sqlite"
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_ledger()

    def _initialize_ledger(self) -> None:
        with sqlite3.connect(self.ledger_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_id TEXT PRIMARY KEY,
                    source_schema TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                )
                """
            )

    def write(
        self,
        event: CdcEvent,
        *,
        ingested_at: datetime | None = None,
    ) -> bool:
        """Grava um evento novo e retorna False para uma reentrega idêntica."""

        event_id = event_id_for(event)
        processed_at = (ingested_at or datetime.now(timezone.utc)).isoformat()

        with sqlite3.connect(self.ledger_path) as connection:
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO processed_events
                    (event_id, source_schema, source_table, processed_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, event.schema, event.table, processed_at),
            ).rowcount

        if inserted == 0:
            return False

        output_path = self.root / "raw" / f"table={event.table}" / "events.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {
            "event_id": event_id,
            "ingested_at": processed_at,
            "schema": event.schema,
            "table": event.table,
            "operation": event.operation,
            "snapshot": event.snapshot,
            "source_lsn": event.source_lsn,
            "transaction_id": event.transaction_id,
            "raw": event.raw,
        }

        with output_path.open("a", encoding="utf-8") as output_file:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

        return True
