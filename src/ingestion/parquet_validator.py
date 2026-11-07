"""Valida arquivos Parquet gerados pela extração batch local."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def validate_dataset(
    dataset_root: Path,
    *,
    expected_columns: list[str],
    primary_key: str,
    required_columns: list[str],
) -> dict[str, Any]:
    """Valida manifesto, schema, contagem, nulos obrigatórios e duplicidade de PK."""
    manifest_path = dataset_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifesto não encontrado: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [dataset_root / name for name in manifest.get("files", [])]
    missing_files = [str(path.name) for path in files if not path.exists()]
    if missing_files:
        raise FileNotFoundError("Arquivos do manifesto ausentes: " + ", ".join(missing_files))

    expected = set(expected_columns)
    actual_schema: list[str] | None = None
    row_count = 0
    null_counts = {column: 0 for column in required_columns}
    primary_keys: set[Any] = set()
    duplicate_count = 0

    for file_path in files:
        parquet_file = pq.ParquetFile(file_path)
        file_columns = parquet_file.schema_arrow.names
        if actual_schema is None:
            actual_schema = file_columns
        if set(file_columns) != expected:
            raise ValueError(
                f"Schema inesperado em {file_path.name}: "
                f"esperado={sorted(expected)}, recebido={file_columns}"
            )

        columns_to_read = list(dict.fromkeys([*expected_columns, primary_key]))
        for batch in parquet_file.iter_batches(columns=columns_to_read):
            row_count += batch.num_rows
            for column in required_columns:
                null_counts[column] += batch.column(column).null_count
            for key in batch.column(primary_key).to_pylist():
                if key in primary_keys:
                    duplicate_count += 1
                else:
                    primary_keys.add(key)

    expected_rows = manifest.get("rows")
    checks = {
        "manifest_status_succeeded": manifest.get("status") == "succeeded",
        "files_exist": not missing_files,
        "row_count_matches_manifest": expected_rows == row_count,
        "primary_key_not_null": null_counts.get(primary_key, 0) == 0,
        "primary_key_unique": duplicate_count == 0,
        "required_columns_not_null": all(value == 0 for value in null_counts.values()),
        "schema_matches_expected": actual_schema is not None and set(actual_schema) == expected,
    }
    return {
        "status": "succeeded" if all(checks.values()) else "failed",
        "dataset": str(dataset_root),
        "rows": row_count,
        "manifest_rows": expected_rows,
        "files": len(files),
        "primary_key": primary_key,
        "duplicate_primary_keys": duplicate_count,
        "required_null_counts": null_counts,
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--columns", nargs="+", required=True)
    parser.add_argument("--primary-key", required=True)
    parser.add_argument("--required-columns", nargs="+", required=True)
    parser.add_argument("--report-path", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = validate_dataset(
        arguments.dataset_root,
        expected_columns=arguments.columns,
        primary_key=arguments.primary_key,
        required_columns=arguments.required_columns,
    )
    if arguments.report_path:
        arguments.report_path.parent.mkdir(parents=True, exist_ok=True)
        arguments.report_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
