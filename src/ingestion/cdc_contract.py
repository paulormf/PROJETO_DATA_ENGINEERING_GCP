"""Contrato mínimo para eventos CDC emitidos pelo Debezium."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VALID_OPERATIONS = frozenset({"r", "c", "u", "d", "t"})


class CdcContractError(ValueError):
    """Indica que um evento não atende ao contrato esperado."""


@dataclass(frozen=True, slots=True)
class CdcEvent:
    """Representação normalizada dos metadados essenciais de um evento CDC."""

    schema: str
    table: str
    operation: str
    source_lsn: int | None
    transaction_id: int | None
    snapshot: bool
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    raw: dict[str, Any]

    @property
    def is_snapshot(self) -> bool:
        """Retorna se o evento foi produzido durante um snapshot inicial."""

        return self.snapshot


def parse_cdc_event(payload: dict[str, Any]) -> CdcEvent:
    """Valida e normaliza um payload JSON do Debezium.

    O envelope original é preservado em ``raw`` para permitir auditoria e
    reprocessamento. A função não modifica o dicionário recebido.
    """

    if not isinstance(payload, dict):
        raise CdcContractError("O payload CDC precisa ser um objeto JSON")

    source = payload.get("source")
    if not isinstance(source, dict):
        raise CdcContractError("O campo 'source' é obrigatório e deve ser um objeto")

    schema = source.get("schema")
    table = source.get("table")
    operation = payload.get("op")

    if not isinstance(schema, str) or not schema:
        raise CdcContractError("source.schema é obrigatório")
    if not isinstance(table, str) or not table:
        raise CdcContractError("source.table é obrigatório")
    if operation not in VALID_OPERATIONS:
        raise CdcContractError(f"Operação CDC inválida: {operation!r}")

    before = payload.get("before")
    after = payload.get("after")
    if before is not None and not isinstance(before, dict):
        raise CdcContractError("before deve ser um objeto ou null")
    if after is not None and not isinstance(after, dict):
        raise CdcContractError("after deve ser um objeto ou null")

    source_lsn = source.get("lsn")
    if source_lsn is not None and not isinstance(source_lsn, int):
        raise CdcContractError("source.lsn deve ser inteiro ou null")

    transaction_id = source.get("txId")
    if transaction_id is not None and not isinstance(transaction_id, int):
        raise CdcContractError("source.txId deve ser inteiro ou null")

    snapshot_value = source.get("snapshot", False)
    snapshot = snapshot_value is True or snapshot_value == "true"

    return CdcEvent(
        schema=schema,
        table=table,
        operation=operation,
        source_lsn=source_lsn,
        transaction_id=transaction_id,
        snapshot=snapshot,
        before=before,
        after=after,
        raw=payload,
    )
