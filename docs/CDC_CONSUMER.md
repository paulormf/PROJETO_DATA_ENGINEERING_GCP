# Consumidor CDC Bronze

## Objetivo

O serviço `ingestion.cdc_push_service` recebe envelopes Pub/Sub push
publicados pelo Debezium e prepara um registro imutavel para a tabela raw CDC
do BigQuery.

O repositorio contem o servico, os testes, o Dockerfile e o Terraform para o
consumidor. O ambiente Composer e o runtime CDC nao ficam ligados durante o
laboratorio; o estado efetivamente implantado deve ser conferido na GCP antes
de uma operacao real.

## Contrato de entrada

O endpoint `POST /pubsub` espera o envelope padrao do Pub/Sub push:

- `message.data`: payload Debezium codificado em Base64;
- `message.messageId`: identificador da mensagem Pub/Sub;
- `message.orderingKey`: chave de ordenacao, quando presente;
- `subscription`: identificacao da assinatura de origem.

O payload Debezium e validado pelo contrato existente em
`src/ingestion/cdc_contract.py`. O envelope original e preservado em
`raw_json`.

## Registro Bronze

O writer produz os seguintes campos logicos:

- `event_id`: SHA-256 deterministico do envelope Debezium;
- `pubsub_message_id` e `ordering_key`;
- `source_schema` e `source_table`;
- `operation`, `snapshot`, `source_lsn` e `transaction_id`;
- `before_json`, `after_json` e `raw_json`;
- `ingested_at`.

O `event_id` e enviado como `insertId` ao BigQuery para reduzir duplicidades
em reentregas. Isso nao substitui a deduplicacao no Silver: o BigQuery trata a
deduplicacao de streaming como best effort, portanto o modelo analitico deve
usar `event_id` e a ordenacao por LSN/transacao.

## Resposta HTTP e retry

- `200`: evento persistido; o Pub/Sub pode confirmar a mensagem;
- `400`: envelope ou payload invalido; a mensagem permanece elegivel para
  retry/DLQ conforme a politica da assinatura;
- `500`: falha de persistencia; o Pub/Sub deve reenviar a mensagem.

`GET /healthz` nao acessa o BigQuery e serve apenas para health check.

## Execucao local

Instale as dependencias de desenvolvimento e execute:

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/unit/test_cdc_push_service.py
```

Para executar o container, a tabela destino sera configurada posteriormente
por `BQ_CDC_TABLE`. A aplicacao nao cria tabelas automaticamente.

## Ativacao futura

Quando o CDC for ativado em um ambiente permanente, o Terraform deve manter:

1. tabela `ecommerce_bronze.cdc_events_raw` e schema controlado;
2. service account do consumidor;
3. permissao de escrita restrita a tabela raw no BigQuery;
4. Cloud Run Service;
5. service account de push e `roles/run.invoker`;
6. 13 assinaturas push, uma para cada tabela CDC v2;
7. dead-letter, ordering, retry e alertas do consumidor.

O desenho Terraform correspondente esta em
`infra/terraform/cloud_run_cdc_consumer/`. A validacao operacional deve
observar especialmente `categorias`, mas o provisionamento e geral para as 13
tabelas. O runbook de sinais e retries esta em
`docs/OBSERVABILITY.md`.
