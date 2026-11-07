import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ingestion.parquet_validator import validate_dataset


def create_dataset(root: Path, rows: list[dict[str, object]]) -> None:
    root.mkdir()
    pq.write_table(pa.Table.from_pylist(rows), root / "part-00000.parquet")
    (root / "manifest.json").write_text(
        json.dumps({"status": "succeeded", "rows": len(rows), "files": ["part-00000.parquet"]}),
        encoding="utf-8",
    )


def test_validate_dataset_accepts_valid_dataset(tmp_path: Path) -> None:
    root = tmp_path / "table=categorias"
    create_dataset(root, [{"categoria_id": 1, "nome_categoria": "Casa"}])

    result = validate_dataset(
        root,
        expected_columns=["categoria_id", "nome_categoria"],
        primary_key="categoria_id",
        required_columns=["categoria_id", "nome_categoria"],
    )

    assert result["status"] == "succeeded"
    assert result["checks"]["primary_key_unique"] is True


def test_validate_dataset_detects_duplicate_primary_key(tmp_path: Path) -> None:
    root = tmp_path / "table=categorias"
    create_dataset(
        root,
        [
            {"categoria_id": 1, "nome_categoria": "Casa"},
            {"categoria_id": 1, "nome_categoria": "Cozinha"},
        ],
    )

    result = validate_dataset(
        root,
        expected_columns=["categoria_id", "nome_categoria"],
        primary_key="categoria_id",
        required_columns=["categoria_id", "nome_categoria"],
    )

    assert result["status"] == "failed"
    assert result["duplicate_primary_keys"] == 1
