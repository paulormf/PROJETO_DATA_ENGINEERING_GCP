"""Plano puro de argumentos para a materializacao Bronze.

Este modulo nao importa Airflow. Ele pode ser testado localmente e e enviado
junto com a DAG para o bucket do Composer. A lista deve permanecer sincronizada
com ``config/ingestion_tables.json``; o teste unitario verifica essa regra.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any


TABLE_NAMES: tuple[str, ...] = (
    "armazens",
    "categorias",
    "clientes",
    "enderecos_clientes",
    "envios",
    "estoque",
    "eventos_clientes",
    "itens_pedido",
    "marcas",
    "pagamentos",
    "pedidos",
    "produtos",
    "variantes_produtos",
)

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,299}$")
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_identifier(value: str, field_name: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} invalido: {value!r}")
    return value


def _validate_run_id(value: str) -> str:
    if not _RUN_ID_PATTERN.fullmatch(value):
        raise ValueError("run_id invalido")
    return value


def _validate_ingestion_date(value: str) -> str:
    if not _DATE_PATTERN.fullmatch(value):
        raise ValueError("ingestion_date deve usar YYYY-MM-DD")
    return value


def build_materializer_overrides(
    table_names: Iterable[str],
    *,
    schema: str,
    run_id: str,
    ingestion_date: str,
    bronze_prefix: str = "bronze/parquet",
) -> list[dict[str, Any]]:
    """Gera os overrides independentes usados pelo operador Cloud Run.

    O Job ja possui projeto, bucket e dataset em variaveis de ambiente. Por
    isso, cada override informa somente os parametros variaveis da tabela e do
    ciclo. A lista ``args`` substitui os argumentos existentes do container;
    ``clear_args`` nao e enviado porque a API do Cloud Run rejeita uma lista
    de argumentos junto com ``clear_args=True``.
    """

    _validate_identifier(schema, "schema")
    _validate_run_id(run_id)
    _validate_ingestion_date(ingestion_date)
    if not bronze_prefix or bronze_prefix.startswith("gs://"):
        raise ValueError("bronze_prefix deve ser um prefixo relativo do bucket")

    tables = tuple(table_names)
    if not tables:
        raise ValueError("ao menos uma tabela deve ser informada")
    if len(set(tables)) != len(tables):
        raise ValueError("a lista de tabelas nao pode conter duplicidades")

    overrides: list[dict[str, Any]] = []
    for table in tables:
        _validate_identifier(table, "tabela")
        overrides.append(
            {
                "container_overrides": [
                    {
                        "args": [
                            "--schema",
                            schema,
                            "--table",
                            table,
                            "--target-table",
                            f"bronze_{table}",
                            "--run-id",
                            run_id,
                            "--ingestion-date",
                            ingestion_date,
                            "--bronze-prefix",
                            bronze_prefix,
                        ],
                    }
                ]
            }
        )
    return overrides
