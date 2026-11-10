from __future__ import annotations

import json
import sys
from typing import Any

from ingestion.dummyjson_products_gcs_job import parse_args, upload_products_to_gcs


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class FakeBlob:
    def __init__(self) -> None:
        self.payload: bytes | None = None
        self.kwargs: dict[str, Any] = {}

    def upload_from_string(self, payload: bytes, **kwargs: Any) -> None:
        self.payload = payload
        self.kwargs = kwargs


class FakeBucket:
    def __init__(self, blob: FakeBlob) -> None:
        self.blob_instance = blob
        self.object_name: str | None = None

    def blob(self, object_name: str) -> FakeBlob:
        self.object_name = object_name
        return self.blob_instance


class FakeStorageClient:
    def __init__(self, bucket: FakeBucket) -> None:
        self.bucket_instance = bucket
        self.bucket_name: str | None = None

    def bucket(self, bucket_name: str) -> FakeBucket:
        self.bucket_name = bucket_name
        return self.bucket_instance


def test_upload_products_to_gcs_writes_immutable_raw_object() -> None:
    blob = FakeBlob()
    bucket = FakeBucket(blob)
    client = FakeStorageClient(bucket)

    def opener(request: object, *, timeout: int) -> FakeResponse:
        return FakeResponse(
            {"products": [{"id": 1, "title": "Produto"}], "total": 1, "skip": 0}
        )

    result = upload_products_to_gcs(
        project_id="project-test",
        bucket_name="bucket-test",
        object_name="raw/api=dummyjson/products/run=run-001/products.json",
        api_url="https://example.test/products",
        opener=opener,
        storage_client=client,
    )

    assert result["gcs_uri"] == (
        "gs://bucket-test/raw/api=dummyjson/products/run=run-001/products.json"
    )
    assert client.bucket_name == "bucket-test"
    assert bucket.object_name == "raw/api=dummyjson/products/run=run-001/products.json"
    assert blob.kwargs == {
        "content_type": "application/json",
        "if_generation_match": 0,
    }
    assert json.loads(blob.payload or b"{}")["products"] == [
        {"id": 1, "title": "Produto"}
    ]


def test_parse_args_maps_bucket_to_function_parameter(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dummyjson_products_gcs_job.py",
            "--bucket",
            "bucket-test",
            "--object-name",
            "raw/products.json",
        ],
    )

    arguments = parse_args()

    assert arguments.bucket_name == "bucket-test"
    assert arguments.object_name == "raw/products.json"
