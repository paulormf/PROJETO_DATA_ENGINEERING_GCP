import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from ingestion.cdc_contract import CdcContractError, parse_cdc_event


def test_parse_snapshot_read_event() -> None:
    payload = {
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

    event = parse_cdc_event(payload)

    assert event.schema == "ecommerce"
    assert event.table == "armazens"
    assert event.operation == "r"
    assert event.is_snapshot is True
    assert event.after == payload["after"]
    assert event.raw is payload


@pytest.mark.parametrize("operation", ["c", "u", "d", "t"])
def test_accepts_supported_operations(operation: str) -> None:
    payload = {
        "before": None,
        "after": None,
        "source": {"schema": "ecommerce", "table": "armazens"},
        "op": operation,
    }

    assert parse_cdc_event(payload).operation == operation


def test_rejects_missing_source_table() -> None:
    payload = {
        "before": None,
        "after": None,
        "source": {"schema": "ecommerce"},
        "op": "r",
    }

    with pytest.raises(CdcContractError, match="source.table"):
        parse_cdc_event(payload)


def test_rejects_invalid_operation() -> None:
    payload = {
        "before": None,
        "after": None,
        "source": {"schema": "ecommerce", "table": "armazens"},
        "op": "x",
    }

    with pytest.raises(CdcContractError, match="Operação CDC inválida"):
        parse_cdc_event(payload)
