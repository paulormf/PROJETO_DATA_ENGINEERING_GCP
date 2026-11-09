# Dataform Silver

Este projeto Dataform transforma as tabelas full da camada Bronze e os eventos
CDC persistidos em `ecommerce_bronze.cdc_events_raw` em tabelas incrementais da
camada `ecommerce_silver`.

## Entradas

- `ecommerce_bronze.bronze_<tabela>`: baseline full materializado pelo
  pipeline de ingestao;
- `ecommerce_bronze.cdc_events_raw`: eventos Debezium entregues por Pub/Sub e
  persistidos pelo consumidor Cloud Run.

## Estrategia

As tabelas Silver sao geradas a partir de um catalogo central em
`includes/table_catalog.js`. Cada modelo usa a chave primaria da origem como
`uniqueKey`, aplica uma janela de reprocessamento de um dia para reduzir o
risco de dados atrasados e preserva `_operation`, `_source_lsn`,
`_is_deleted` e `_ingested_at`.

As acoes repetitivas sao geradas com JavaScript oficial do Dataform para
evitar 13 blocos SQLX quase identicos. A consulta SQL de cada tabela continua
explicita no codigo gerado; modelos semanticos e data marts serao adicionados
como SQLX dedicado nas fases seguintes.

O primeiro ciclo combina o baseline full com os eventos CDC. Os ciclos
incrementais processam apenas o CDC recente e usam `MERGE` por chave primaria.
Deletes permanecem como registros logicos para auditoria; consumidores
analiticos devem filtrar `_is_deleted = FALSE` quando desejarem somente o
estado ativo.

## Validacao

Antes da primeira execucao cloud, o projeto deve ser compilado e o grafo
inspecionado. Depois da materializacao, as assertions de integridade de chave
primaria devem retornar zero linhas.

A criacao do repositorio Dataform e a execucao do workflow cloud sao etapas
separadas e exigem aprovacao explicita.
