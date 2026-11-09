"""Contrato de coordenacao entre uma carga full e um ciclo CDC."""

from __future__ import annotations

from dataclasses import dataclass
import re


_EPOCH_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_PG_LSN_PATTERN = re.compile(r"([0-9A-Fa-f]+)/([0-9A-Fa-f]+)")


@dataclass(frozen=True, slots=True)
class CdcEpoch:
    """Identifica o ponto anterior ao full a partir do qual o CDC sera reaplicado."""

    epoch_id: str
    start_lsn: str
    start_lsn_int: int


def pg_lsn_to_int(value: str) -> int:
    """Converte um `pg_lsn` hexadecimal para o inteiro usado pelo Debezium."""

    if not isinstance(value, str):
        raise ValueError("cdc_start_lsn deve ser texto no formato HEX/HEX")
    match = _PG_LSN_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError("cdc_start_lsn deve usar o formato PostgreSQL HEX/HEX")
    return (int(match.group(1), 16) << 32) + int(match.group(2), 16)


def build_cdc_epoch(epoch_id: str | None, start_lsn: str | None) -> CdcEpoch | None:
    """Valida metadados opcionais; ambos devem existir para um full coordenado."""

    if epoch_id is None and start_lsn is None:
        return None
    if not epoch_id or not start_lsn:
        raise ValueError("cdc_epoch_id e cdc_start_lsn devem ser informados juntos")
    if _EPOCH_ID_PATTERN.fullmatch(epoch_id) is None:
        raise ValueError("cdc_epoch_id contem caracteres invalidos")
    normalized_lsn = start_lsn.strip().upper()
    return CdcEpoch(
        epoch_id=epoch_id,
        start_lsn=normalized_lsn,
        start_lsn_int=pg_lsn_to_int(normalized_lsn),
    )
