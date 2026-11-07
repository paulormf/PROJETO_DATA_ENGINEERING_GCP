"""Leitura e validacao do catalogo de tabelas de ingestao."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ingestion.postgres_parquet_exporter import validate_identifier


@dataclass(frozen=True)
class TableSpec:
    name: str
    primary_key: tuple[str, ...]
    batch_size: int
    load_order: int
    watermark_candidate: str | None = None
    event_time_column: str | None = None
    observed_rows: int | None = None


@dataclass(frozen=True)
class IngestionCatalog:
    database: str
    schema: str
    default_batch_size: int
    tables: tuple[TableSpec, ...]


def _optional_identifier(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return validate_identifier(str(value), field_name)


def load_catalog(path: str | Path) -> IngestionCatalog:
    catalog_path = Path(path)
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("catalogo deve ser um objeto JSON")

    source = payload.get("source")
    initial_load = payload.get("initial_load")
    raw_tables = payload.get("tables")
    if not isinstance(source, dict) or not isinstance(initial_load, dict):
        raise ValueError("catalogo deve conter source e initial_load")
    if not isinstance(raw_tables, list) or not raw_tables:
        raise ValueError("catalogo deve conter pelo menos uma tabela")

    database = str(source.get("database", "")).strip()
    schema = validate_identifier(str(source.get("schema", "")), "schema")
    default_batch_size = int(initial_load.get("default_batch_size", 10_000))
    if not database or default_batch_size <= 0:
        raise ValueError("database e default_batch_size devem ser validos")

    tables: list[TableSpec] = []
    names: set[str] = set()
    for raw_table in raw_tables:
        if not isinstance(raw_table, dict):
            raise ValueError("cada tabela do catalogo deve ser um objeto")
        name = validate_identifier(str(raw_table.get("name", "")), "tabela")
        if name in names:
            raise ValueError(f"tabela duplicada no catalogo: {name}")
        names.add(name)

        raw_primary_key = raw_table.get("primary_key")
        if not isinstance(raw_primary_key, list) or not raw_primary_key:
            raise ValueError(f"PK ausente para a tabela {name}")
        primary_key = tuple(
            validate_identifier(str(column), "coluna de PK")
            for column in raw_primary_key
        )
        batch_size = int(raw_table.get("batch_size", default_batch_size))
        load_order = int(raw_table.get("load_order", 1))
        if batch_size <= 0 or load_order <= 0:
            raise ValueError(f"batch_size/load_order invalidos para {name}")

        observed_rows = raw_table.get("observed_rows")
        tables.append(
            TableSpec(
                name=name,
                primary_key=primary_key,
                batch_size=batch_size,
                load_order=load_order,
                watermark_candidate=_optional_identifier(
                    raw_table.get("watermark_candidate"), "watermark"
                ),
                event_time_column=_optional_identifier(
                    raw_table.get("event_time_column"), "tempo de evento"
                ),
                observed_rows=int(observed_rows) if observed_rows is not None else None,
            )
        )

    return IngestionCatalog(
        database=database,
        schema=schema,
        default_batch_size=default_batch_size,
        tables=tuple(sorted(tables, key=lambda table: (table.load_order, table.name))),
    )

