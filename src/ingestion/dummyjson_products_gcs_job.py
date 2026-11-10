"""Extrai produtos da DummyJSON e grava um envelope Raw imutável no GCS."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable

from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

from ingestion.dummyjson_products_extractor import (
    DEFAULT_API_URL,
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT_SECONDS,
    build_raw_envelope,
    fetch_all_products,
)


def upload_products_to_gcs(
    *,
    bucket_name: str,
    object_name: str,
    project_id: str | None = None,
    api_url: str = DEFAULT_API_URL,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_records: int | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    opener: Callable[..., Any] | None = None,
    sleeper: Callable[[float], None] | None = None,
    storage_client: Any | None = None,
) -> dict[str, Any]:
    """Extrai e grava no GCS sem sobrescrever o mesmo objeto lógico."""
    if not bucket_name.strip():
        raise ValueError("bucket_name nao pode ser vazio")
    if not object_name.strip() or object_name.endswith("/"):
        raise ValueError("object_name deve ser um caminho de objeto valido")

    fetch_kwargs: dict[str, Any] = {
        "api_url": api_url,
        "page_size": page_size,
        "max_records": max_records,
        "timeout_seconds": timeout_seconds,
        "max_retries": max_retries,
        "backoff_seconds": backoff_seconds,
    }
    if opener is not None:
        fetch_kwargs["opener"] = opener
    if sleeper is not None:
        fetch_kwargs["sleeper"] = sleeper

    products = fetch_all_products(**fetch_kwargs)
    envelope = build_raw_envelope(
        products,
        api_url=api_url,
        page_size=page_size,
    )
    payload = json.dumps(envelope, ensure_ascii=False).encode("utf-8")

    client = storage_client or storage.Client(project=project_id)
    blob = client.bucket(bucket_name).blob(object_name)
    try:
        blob.upload_from_string(
            payload,
            content_type="application/json",
            if_generation_match=0,
        )
    except PreconditionFailed as exc:
        raise RuntimeError(
            f"o objeto gs://{bucket_name}/{object_name} ja existe; "
            "use um novo object_name para uma nova execucao"
        ) from exc

    return {
        "status": "succeeded",
        "source_system": envelope["source_system"],
        "gcs_uri": f"gs://{bucket_name}/{object_name}",
        "records": len(products),
        "bytes": len(payload),
        "extracted_at": envelope["extracted_at"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", default=os.getenv("GCP_PROJECT_ID"))
    parser.add_argument("--bucket", dest="bucket_name", required=True)
    parser.add_argument("--object-name", required=True)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max-records", type=int)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--backoff-seconds", type=float, default=DEFAULT_BACKOFF_SECONDS)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(upload_products_to_gcs(**vars(parse_args())), indent=2))
