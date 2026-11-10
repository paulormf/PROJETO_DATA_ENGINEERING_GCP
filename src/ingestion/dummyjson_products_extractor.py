"""Extrai produtos paginados da API publica DummyJSON para um arquivo Raw JSON."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_API_URL = "https://dummyjson.com/products"
DEFAULT_PAGE_SIZE = 30
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 1.0
RETRYABLE_HTTP_STATUS = frozenset({429, 500, 502, 503, 504})
USER_AGENT = "projeto-data-engineering-gcp/api-extractor/1.0"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _page_url(api_url: str, *, limit: int, skip: int) -> str:
    parsed = urlsplit(api_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"limit": str(limit), "skip": str(skip)})
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _request_json(
    url: str,
    *,
    timeout_seconds: int,
    max_retries: int,
    backoff_seconds: float,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )

    for attempt in range(max_retries + 1):
        try:
            with opener(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("a resposta da API deve ser um objeto JSON")
            return payload
        except HTTPError as exc:
            retryable = exc.code in RETRYABLE_HTTP_STATUS
            if not retryable or attempt >= max_retries:
                raise RuntimeError(
                    f"falha HTTP permanente na API: status={exc.code}"
                ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            if attempt >= max_retries:
                raise RuntimeError("falha de rede permanente na API") from exc

        sleeper(backoff_seconds * (2**attempt))

    raise RuntimeError("a API excedeu o numero maximo de tentativas")


def _validate_page(
    payload: dict[str, Any],
    *,
    expected_skip: int,
) -> tuple[list[dict[str, Any]], int]:
    products = payload.get("products")
    total = payload.get("total")
    response_skip = payload.get("skip")

    if not isinstance(products, list):
        raise ValueError("a resposta da API nao possui products como lista")
    if not isinstance(total, int) or total < 0:
        raise ValueError("a resposta da API nao possui total inteiro valido")
    if response_skip != expected_skip:
        raise ValueError(
            "a resposta da API retornou skip inesperado: "
            f"esperado={expected_skip}, recebido={response_skip}"
        )
    if not all(isinstance(product, dict) for product in products):
        raise ValueError("a lista products contem registros que nao sao objetos JSON")

    return products, total


def fetch_all_products(
    *,
    api_url: str = DEFAULT_API_URL,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_records: int | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Busca todas as paginas da API, ou ate atingir max_records."""
    if not api_url.startswith(("http://", "https://")):
        raise ValueError("api_url deve usar http:// ou https://")
    if page_size <= 0:
        raise ValueError("page_size deve ser maior que zero")
    if max_records is not None and max_records <= 0:
        raise ValueError("max_records deve ser maior que zero")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds deve ser maior que zero")
    if max_retries < 0:
        raise ValueError("max_retries nao pode ser negativo")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds nao pode ser negativo")

    products: list[dict[str, Any]] = []
    skip = 0
    expected_total: int | None = None

    while expected_total is None or skip < expected_total:
        payload = _request_json(
            _page_url(api_url, limit=page_size, skip=skip),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            backoff_seconds=backoff_seconds,
            opener=opener,
            sleeper=sleeper,
        )
        page_products, page_total = _validate_page(payload, expected_skip=skip)
        expected_total = page_total if expected_total is None else expected_total

        if page_total != expected_total:
            raise ValueError("o total da API mudou durante a paginação")
        if not page_products:
            break

        remaining = None if max_records is None else max_records - len(products)
        if remaining is not None:
            products.extend(page_products[:remaining])
            if len(products) >= max_records:
                break
        else:
            products.extend(page_products)

        next_skip = skip + len(page_products)
        if next_skip <= skip:
            raise ValueError("a paginação da API nao avancou")
        skip = next_skip

    return products


def build_raw_envelope(
    products: list[dict[str, Any]],
    *,
    api_url: str,
    page_size: int,
    extracted_at: str | None = None,
) -> dict[str, Any]:
    """Monta o contrato Raw compartilhado pelo destino local e pelo GCS."""
    return {
        "source_system": "dummyjson_products_api",
        "source_url": api_url,
        "extracted_at": extracted_at or _utc_now(),
        "page_size": page_size,
        "record_count": len(products),
        "products": products,
    }


def extract_products_to_file(
    *,
    output_path: str | Path,
    api_url: str = DEFAULT_API_URL,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_records: int | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Extrai a API e grava um envelope Raw JSON atomicamente em disco."""
    products = fetch_all_products(
        api_url=api_url,
        page_size=page_size,
        max_records=max_records,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        backoff_seconds=backoff_seconds,
        opener=opener,
        sleeper=sleeper,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(f".{output.name}.tmp")
    envelope = build_raw_envelope(
        products,
        api_url=api_url,
        page_size=page_size,
    )
    temporary_output.write_text(
        json.dumps(envelope, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_output.replace(output)
    return {
        "status": "succeeded",
        "source_system": envelope["source_system"],
        "output": str(output),
        "records": len(products),
        "extracted_at": envelope["extracted_at"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        dest="output_path",
        required=True,
        help="Arquivo Raw JSON de destino",
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--max-records", type=int)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--backoff-seconds", type=float, default=DEFAULT_BACKOFF_SECONDS)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(extract_products_to_file(**vars(parse_args())), indent=2))
