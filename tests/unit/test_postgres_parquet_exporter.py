from pathlib import Path

import pyarrow.parquet as pq
import pytest

from ingestion.postgres_parquet_exporter import (
    validate_identifier,
    write_parquet_batch,
)


def test_validate_identifier_accepts_simple_name() -> None:
    assert validate_identifier("categorias", "tabela") == "categorias"


@pytest.mark.parametrize("value", ["ecommerce.categorias", "categorias;DROP TABLE x", ""])
def test_validate_identifier_rejects_sql_injection_or_empty(value: str) -> None:
    with pytest.raises(ValueError):
        validate_identifier(value, "tabela")


def test_write_parquet_batch_preserves_rows_and_compression(tmp_path: Path) -> None:
    output = tmp_path / "part-00000.parquet"
    rows = [
        {"categoria_id": 1, "categoria_pai_id": None, "nome_categoria": "Casa"},
        {"categoria_id": 2, "categoria_pai_id": 1, "nome_categoria": "Cozinha"},
    ]

    assert write_parquet_batch(rows, output) == 2
    loaded = pq.read_table(output)
    assert loaded.num_rows == 2
    assert loaded.column_names == ["categoria_id", "categoria_pai_id", "nome_categoria"]
    assert loaded.schema.metadata is None


def test_write_parquet_batch_does_not_create_file_for_empty_batch(tmp_path: Path) -> None:
    output = tmp_path / "empty.parquet"
    assert write_parquet_batch([], output) == 0
    assert not output.exists()
