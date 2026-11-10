# Dataflow

## Batch

Os pipelines em `src/dataflow/` processam lotes finitos. A imagem e o Flex
Template podem permanecer publicados no Artifact Registry/GCS, mas os workers
existem somente durante a execução do job. O modo operacional recomendado para
este laboratorio é iniciar, observar `JOB_STATE_DONE`/falha, verificar DLQ e
encerrar a execução.

## Streaming

`streaming/` contém um template isolado para estudar Apache Beam Streaming.
Ele não é criado por Terraform, não é iniciado pelo CI/CD e não deve apontar
para o Pub/Sub real do Debezium. O workflow correspondente é manual e publica
artefatos; não inicia um job contínuo.

## Controle de custos

- Não há serviço Dataflow permanentemente ativo neste repositorio.
- Não executar esse template como streaming contínuo durante a etapa de estudo.
- Para experimentos, usar poucos eventos, janela curta e `drain`/`cancel` ao
  terminar.
- Revisar objetos antigos de template, DLQ e temporários conforme a política
  de retenção do bucket.
