"""Exporta uma tabela PostgreSQL em lotes para arquivos Parquet locais.

Este módulo é uma etapa de laboratório: não cria recursos GCP e não envia dados
para a nuvem. A conexão é somente leitura e usa cursor server-side para evitar
carregar a tabela inteira na memória.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq
import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row


IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(value: str, label: str) -> str:
    """Valida um nome simples de schema/tabela antes de compor SQL."""
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def write_parquet_batch(rows: list[dict[str, Any]], output_path: Path) -> int:
    """Escreve um lote e retorna a quantidade de linhas gravadas."""
    if not rows:
        return 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, output_path, compression="snappy")
    return table.num_rows


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def export_table(
    *,
    schema: str,
    table: str,
    output_root: Path,
    batch_size: int = 10_000,
) -> dict[str, Any]:
    """Executa uma exportação consistente e somente leitura."""
    schema = validate_identifier(schema, "schema")
    table = validate_identifier(table, "tabela")
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero")

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    required = ("POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Variáveis ausentes no .env: " + ", ".join(missing))

    connect_kwargs = {
        "host": os.environ["POSTGRES_HOST"],
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DBNAME", "appdb"),
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "row_factory": dict_row,
    }
    table_root = output_root / f"table={table}"
    started_at = _utc_now()
    files: list[str] = []
    row_count = 0
    batch_count = 0

    with psycopg.connect(**connect_kwargs) as connection:
        connection.execute(
            "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        )
        with connection.cursor(name=f"export_{table}") as cursor:
            cursor.execute(
                sql.SQL("SELECT * FROM {}.{} ORDER BY 1").format(
                    sql.Identifier(schema), sql.Identifier(table)
                )
            )
            while rows := cursor.fetchmany(batch_size):
                file_name = f"part-{batch_count:05d}.parquet"
                output_path = table_root / file_name
                written = write_parquet_batch(rows, output_path)
                files.append(file_name)
                row_count += written
                batch_count += 1

    manifest = {
        "status": "succeeded",
        "source": {"schema": schema, "table": table},
        "rows": row_count,
        "batches": batch_count,
        "files": files,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "format": "parquet",
        "compression": "snappy",
    }
    table_root.mkdir(parents=True, exist_ok=True)
    (table_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", default="ecommerce")
    parser.add_argument("--table", default="categorias")
    parser.add_argument("--output-root", type=Path, default=Path("data/local/full_extract"))
    parser.add_argument("--batch-size", type=int, default=10_000)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(export_table(**vars(parse_args())), indent=2, ensure_ascii=False))
