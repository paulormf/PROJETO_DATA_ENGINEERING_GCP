from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from ingestion.dummyjson_products_extractor import (
    build_raw_envelope,
    extract_products_to_file,
    fetch_all_products,
)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def page(*, products: list[dict[str, object]], total: int, skip: int) -> dict[str, object]:
    return {"products": products, "total": total, "skip": skip, "limit": len(products)}


def test_fetch_all_products_paginates_and_respects_max_records() -> None:
    requested_urls: list[str] = []
    responses = iter(
        [
            page(products=[{"id": 1}, {"id": 2}], total=4, skip=0),
            page(products=[{"id": 3}, {"id": 4}], total=4, skip=2),
        ]
    )

    def opener(request: object, *, timeout: int) -> FakeResponse:
        requested_urls.append(request.full_url)  # type: ignore[attr-defined]
        return FakeResponse(next(responses))

    products = fetch_all_products(
        api_url="https://example.test/products",
        page_size=2,
        max_records=3,
        opener=opener,
    )

    assert products == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert "limit=2&skip=0" in requested_urls[0]
    assert "limit=2&skip=2" in requested_urls[1]


def test_fetch_all_products_retries_transient_http_error() -> None:
    calls = 0
    sleep_calls: list[float] = []

    def opener(request: object, *, timeout: int) -> FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPError(request.full_url, 503, "temporary", {}, io.BytesIO())  # type: ignore[attr-defined]
        return FakeResponse(page(products=[{"id": 1}], total=1, skip=0))

    products = fetch_all_products(
        api_url="https://example.test/products",
        page_size=1,
        max_retries=1,
        backoff_seconds=2,
        opener=opener,
        sleeper=sleep_calls.append,
    )

    assert products == [{"id": 1}]
    assert calls == 2
    assert sleep_calls == [2]


def test_fetch_all_products_rejects_invalid_envelope() -> None:
    def opener(request: object, *, timeout: int) -> FakeResponse:
        return FakeResponse({"products": {"id": 1}, "total": 1, "skip": 0})

    with pytest.raises(ValueError, match="products como lista"):
        fetch_all_products(
            api_url="https://example.test/products",
            opener=opener,
        )


def test_extract_products_to_file_writes_raw_envelope(tmp_path: Path) -> None:
    def opener(request: object, *, timeout: int) -> FakeResponse:
        return FakeResponse(page(products=[{"id": 1, "title": "Produto"}], total=1, skip=0))

    output = tmp_path / "raw" / "products.json"
    result = extract_products_to_file(
        output_path=output,
        api_url="https://example.test/products",
        opener=opener,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "succeeded"
    assert result["records"] == 1
    assert payload["source_system"] == "dummyjson_products_api"
    assert payload["record_count"] == 1
    assert payload["products"] == [{"id": 1, "title": "Produto"}]


def test_build_raw_envelope_preserves_contract() -> None:
    envelope = build_raw_envelope(
        [{"id": 1}],
        api_url="https://example.test/products",
        page_size=30,
        extracted_at="2026-11-10T00:00:00+00:00",
    )

    assert envelope == {
        "source_system": "dummyjson_products_api",
        "source_url": "https://example.test/products",
        "extracted_at": "2026-11-10T00:00:00+00:00",
        "page_size": 30,
        "record_count": 1,
        "products": [{"id": 1}],
    }
