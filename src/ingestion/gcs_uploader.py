"""Upload idempotente de um dataset local validado para o Cloud Storage."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage


def file_md5_base64(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode("ascii")


def _content_type(path: Path) -> str:
    if path.suffix == ".parquet":
        return "application/vnd.apache.parquet"
    if path.suffix == ".json":
        return "application/json"
    return "application/octet-stream"


def _safe_manifest_file(name: str) -> str:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts or relative.name != name:
        raise ValueError(f"Nome de arquivo inválido no manifesto: {name!r}")
    return name


def upload_file_idempotent(
    bucket: Any,
    local_path: Path,
    object_name: str,
) -> dict[str, Any]:
    """Cria o objeto uma vez; reexecuções aceitam o mesmo conteúdo."""
    blob = bucket.blob(object_name)
    local_md5 = file_md5_base64(local_path)
    try:
        blob.upload_from_filename(
            local_path,
            content_type=_content_type(local_path),
            if_generation_match=0,
        )
        return {"object": object_name, "status": "uploaded", "bytes": local_path.stat().st_size}
    except PreconditionFailed:
        blob.reload()
        if blob.size != local_path.stat().st_size or blob.md5_hash != local_md5:
            raise RuntimeError(f"Objeto existente tem conteúdo diferente: gs://{bucket.name}/{object_name}")
        return {"object": object_name, "status": "already_exists_same_content", "bytes": blob.size}


def upload_dataset(
    *,
    project_id: str,
    bucket_name: str,
    source_dir: Path,
    object_prefix: str,
) -> dict[str, Any]:
    manifest_path = source_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "succeeded":
        raise ValueError("Somente datasets com manifesto succeeded podem ser enviados")

    local_names = [_safe_manifest_file(name) for name in manifest.get("files", [])]
    local_names.append("manifest.json")
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    results = []
    for name in local_names:
        local_path = source_dir / name
        if not local_path.is_file():
            raise FileNotFoundError(f"Arquivo do manifesto não encontrado: {local_path}")
        results.append(upload_file_idempotent(bucket, local_path, f"{object_prefix.rstrip('/')}/{name}"))

    return {
        "status": "succeeded",
        "bucket": bucket_name,
        "object_prefix": object_prefix.rstrip("/"),
        "objects": results,
        "object_count": len(results),
        "manifest_rows": manifest.get("rows"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID"), required=not os.getenv("GCP_PROJECT_ID"))
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--object-prefix", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(upload_dataset(**vars(parse_args())), indent=2, ensure_ascii=False))
