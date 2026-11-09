import pytest

from ingestion.cdc_epoch import build_cdc_epoch, pg_lsn_to_int


def test_pg_lsn_to_int_matches_debezium_decimal_lsn() -> None:
    assert pg_lsn_to_int("1/71AB5788") == 6202021768


def test_build_cdc_epoch_normalizes_lsn() -> None:
    epoch = build_cdc_epoch("epoch_20261109_001", "1/71ab5788")

    assert epoch is not None
    assert epoch.epoch_id == "epoch_20261109_001"
    assert epoch.start_lsn == "1/71AB5788"
    assert epoch.start_lsn_int == 6202021768


def test_build_cdc_epoch_accepts_uncoordinated_full() -> None:
    assert build_cdc_epoch(None, None) is None


@pytest.mark.parametrize(
    ("epoch_id", "start_lsn"),
    [("epoch_001", None), (None, "1/71AB5788")],
)
def test_build_cdc_epoch_requires_both_values(
    epoch_id: str | None, start_lsn: str | None
) -> None:
    with pytest.raises(ValueError, match="informados juntos"):
        build_cdc_epoch(epoch_id, start_lsn)


@pytest.mark.parametrize("value", ["", "6202029960", "1-71AB5788", "G/1"])
def test_pg_lsn_to_int_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="HEX/HEX"):
        pg_lsn_to_int(value)
