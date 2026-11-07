"""Leitor Pull controlado para validar eventos CDC no Pub/Sub."""

from __future__ import annotations

import argparse
import base64
import json
from typing import Any

from google.cloud import pubsub_v1

from ingestion.cdc_contract import CdcEvent, parse_cdc_event


def decode_cdc_message(data: bytes) -> CdcEvent:
    """Decodifica os bytes publicados pelo sink Pub/Sub do Debezium."""

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("A mensagem não contém JSON UTF-8 válido") from exc

    return parse_cdc_event(payload)


def summarize_event(
    event: CdcEvent,
    *,
    message_id: str,
    ordering_key: str,
) -> dict[str, Any]:
    """Produz uma saída segura, sem imprimir o payload de negócio."""

    return {
        "message_id": message_id,
        "ordering_key": ordering_key,
        "schema": event.schema,
        "table": event.table,
        "operation": event.operation,
        "snapshot": event.is_snapshot,
        "source_lsn": event.source_lsn,
        "transaction_id": event.transaction_id,
    }


def pull_cdc_messages(
    *,
    project_id: str,
    subscription_id: str,
    max_messages: int,
    acknowledge: bool = False,
    timeout_seconds: float = 15.0,
) -> list[dict[str, Any]]:
    """Lê uma amostra de eventos e opcionalmente confirma mensagens válidas.

    A confirmação é desabilitada por padrão. Em um consumidor real, o ack
    deve ocorrer somente depois da persistência durável do evento.
    """

    if max_messages < 1:
        raise ValueError("max_messages precisa ser maior que zero")

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_id)
    request = pubsub_v1.types.PullRequest(
        subscription=subscription_path,
        max_messages=max_messages,
    )

    response = subscriber.pull(request=request, timeout=timeout_seconds)
    summaries: list[dict[str, Any]] = []
    ack_ids: list[str] = []

    try:
        for received_message in response.received_messages:
            event = decode_cdc_message(received_message.message.data)
            summaries.append(
                summarize_event(
                    event,
                    message_id=received_message.message.message_id,
                    ordering_key=received_message.message.ordering_key,
                )
            )
            ack_ids.append(received_message.ack_id)

        if acknowledge and ack_ids:
            subscriber.acknowledge(
                request={
                    "subscription": subscription_path,
                    "ack_ids": ack_ids,
                }
            )
    finally:
        subscriber.close()

    return summaries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--max-messages", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument(
        "--ack",
        action="store_true",
        help="Confirma mensagens válidas; não usar antes da persistência real.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summaries = pull_cdc_messages(
        project_id=args.project_id,
        subscription_id=args.subscription_id,
        max_messages=args.max_messages,
        acknowledge=args.ack,
        timeout_seconds=args.timeout_seconds,
    )

    print(json.dumps({"count": len(summaries), "events": summaries}, indent=2))


if __name__ == "__main__":
    main()
