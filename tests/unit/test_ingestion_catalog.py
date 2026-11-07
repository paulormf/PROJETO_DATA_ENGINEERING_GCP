from pathlib import Path

import pytest

from ingestion.ingestion_catalog import load_catalog


def test_load_catalog_reads_all_source_tables() -> None:
    catalog = load_catalog(Path("config/ingestion_tables.json"))

    assert catalog.database == "appdb"
    assert catalog.schema == "ecommerce"
    assert len(catalog.tables) == 13
    assert catalog.tables[0].name == "armazens"
    assert next(table for table in catalog.tables if table.name == "estoque").primary_key == (
        "armazem_id",
        "variante_id",
    )


def test_load_catalog_rejects_duplicate_tables(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        '{"source":{"database":"appdb","schema":"ecommerce"},'
        '"initial_load":{"default_batch_size":1000},'
        '"tables":[{"name":"categorias","primary_key":["categoria_id"]},'
        '{"name":"categorias","primary_key":["categoria_id"]}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="tabela duplicada"):
        load_catalog(path)
