# Runbook operacional de baixo custo

Um runbook é o manual de operação de uma plataforma: descreve o que executar,
como confirmar sucesso, como investigar falhas e como interromper recursos para
evitar custo ou processamento indevido. Este documento cobre o laboratório e
serve como base para um ambiente produtivo.

## Princípios

- cada execução deve ter `run_id` ou `batch_id` rastreável;
- objetos Raw são imutáveis e não devem ser sobrescritos;
- retries devem reutilizar o identificador somente quando a etapa for segura;
- a Bronze preserva o recebido; regras de negócio ficam na Silver/Gold;
- nenhuma etapa é considerada concluída apenas porque o container iniciou:
  confirme o status final, a contagem e o destino.

## O que fica desligado

Nao executar neste momento:

- `terraform apply` no modulo Composer;
- jobs Dataflow Streaming de longa duração;
- workflows de publicação por push que iniciem recursos de processamento.

O CI de testes pode continuar sendo executado normalmente, pois não cria
recursos GCP.

## Execução manual da API

1. Executar o Cloud Run Job `ecommerce-api-extract` com um `object_name` novo.
2. Conferir `status=succeeded`, `records` e `gcs_uri` nos logs.
3. Executar o Flex Template Dataflow Batch com o URI retornado, um `batch_id`
   novo e a tabela Bronze configurada.
4. Confirmar `JOB_STATE_DONE` e ausência de arquivos no prefixo de DLQ.
5. Executar a compilação/invocação Dataform apenas para os alvos externos
   necessários.
6. Consultar a Silver e as assertions no BigQuery.

O DAG futuro `ecommerce_external_sources` automatiza essa sequência, mas só
deve ser enviado ao Composer quando o ambiente estiver ligado.

## Execução manual do laboratório Streaming

O workflow `deploy-dataflow-templates.yml` é manual e publica somente a
imagem/template. Ele não inicia um job. Para um experimento controlado:

1. Criar ou escolher uma assinatura e tópico sintéticos;
2. executar o template com janela, lateness e DLQ explícitos;
3. publicar poucos eventos de teste;
4. verificar tabela shadow e DLQ;
5. fazer drain/cancel do job assim que o teste terminar.

Nao apontar esse laboratório para as assinaturas reais do Debezium; o CDC já
possui o consumidor próprio em Cloud Run.

## Conferências antes de reprocessar

- O objeto Raw de entrada existe e é o lote correto.
- O `batch_id` ainda não foi processado na tabela Bronze.
- A tabela destino e a região do Dataflow são compatíveis.
- O prefixo de DLQ é exclusivo do lote.
- O Dataform está compilado a partir do commit esperado.

## Gatilhos CI/CD

- `ci.yml`: testes Python e sintaxe das DAGs em push/PR.
- `ci-dataform.yml`: compilação Dataform em alterações de modelos.
- `deploy-cloud-run-images.yml`: publicação/atualização de imagens quando os
  caminhos `src/ingestion/**` ou `src/materialization/**` mudam; alterações
  exclusivas em `src/dataflow/**` não acionam esse deploy.
- `deploy-composer-dags.yml`: apenas execução manual, sem Composer automático.
- `deploy-dataflow-templates.yml`: apenas execução manual, sem job Streaming
  automático.
