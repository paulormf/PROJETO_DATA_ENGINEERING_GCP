"""Opcoes compartilhadas pelos pipelines Beam batch do projeto."""

from __future__ import annotations

import argparse

from apache_beam.options.pipeline_options import PipelineOptions


class BatchPipelineOptions(PipelineOptions):
    """Argumentos comuns aos templates Dataflow batch."""

    @classmethod
    def _add_argparse_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--input", help="URI de entrada local ou gs://")
        parser.add_argument("--output", help="Prefixo JSONL valido opcional")
        parser.add_argument(
            "--dead-letter-output",
            "--dead_letter_output",
            dest="dead_letter_output",
            help="Prefixo JSONL de rejeitos",
        )
        parser.add_argument(
            "--bigquery-table",
            "--bigquery_table",
            dest="bigquery_table",
            help="Tabela BigQuery completa: projeto:dataset.tabela",
        )
        parser.add_argument(
            "--source-system",
            "--source_system",
            dest="source_system",
            help="Nome logico da fonte de dados",
        )
        parser.add_argument("--batch-id", "--batch_id", dest="batch_id")
        parser.add_argument(
            "--ingested-at",
            "--ingested_at",
            dest="ingested_at",
            help="Timestamp ISO-8601 da ingestao",
        )
