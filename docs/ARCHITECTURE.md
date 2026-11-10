# Arquitetura do projeto

Este repositorio e um monorepo de Engenharia de Dados. O desenho foi mantido
modular para representar fontes diferentes sem transformar cada fonte em um
framework novo.

## Fluxo principal

```text
PostgreSQL
  ├─ carga full -> Cloud Run Job -> GCS Raw/Bronze -> Cloud Run materializer -> BigQuery Bronze
  └─ CDC Debezium -> Pub/Sub -> Cloud Run consumer -> BigQuery Bronze CDC

API DummyJSON -> Cloud Run Job -> GCS Raw imutavel -> Dataflow Batch -> BigQuery Bronze
Fornecedor CSV -> Dataflow Batch -> BigQuery Bronze

BigQuery Bronze -> Dataform -> Silver -> Gold/marts/assertions
```

O Dataform consolida o estado atual das fontes externas e reconcilia o catalogo
PostgreSQL/API/fornecedor no mart `ecommerce_gold.mart_catalogo_reconciliado`.

## Estado econômico do laboratório

- O Composer nao e provisionado neste momento. As DAGs continuam versionadas
  e prontas para uma ativacao futura.
- O workflow de DAGs do Composer e somente `workflow_dispatch`; um push comum
  nao faz upload nem aciona recurso pago.
- Dataflow Batch e executado apenas sob demanda. Ao terminar, o job libera os
  workers; o template e a imagem ficam armazenados e podem gerar somente o
  custo normal de armazenamento.
- O pipeline Dataflow Streaming e um laboratorio isolado. Ele nao usa os
  topicos reais do Debezium, nao e iniciado por CI/CD e nao existe um job
  Streaming permanente no Terraform.
- Cloud Run Jobs nao ficam executando continuamente. Eles sobem apenas quando
  chamados pelo Console, terminal ou orquestrador.

## Repositórios e responsabilidades

| Camada | Local | Responsabilidade |
| --- | --- | --- |
| Ingestao Python | `src/ingestion/` | Extratores, contratos Raw e escrita no GCS |
| Dataflow Batch | `src/dataflow/` | Validacao/normalizacao distribuida de API e CSV |
| Dataflow Streaming | `src/dataflow/pubsub_streaming_shadow.py` | Laboratorio manual de janelas, event-time, deduplicacao e DLQ |
| Dataform | `definitions/`, `includes/` | Modelagem Silver/Gold e assertions |
| Orquestracao | `orchestration/composer/dags/` | DAGs futuras, sem provisionar Composer agora |
| Infraestrutura | `infra/terraform/` | Recursos GCP declarativos e identidades |
| CI/CD | `.github/workflows/` | Testes sempre; imagens e DAGs somente conforme gatilho |

## Idempotencia e recuperação

- Objetos Raw da API usam caminhos únicos por lote, a escrita usa
  `if_generation_match=0` e uma reexecução do mesmo objeto retorna
  `already_exists`, sem sobrescrever o artefato.
- Manifestos de carga full e `batch_id` permitem rastrear uma execução.
- Bronze externo é append-only; Silver escolhe a versão mais recente pela
  chave de negócio e timestamps de origem/ingestao.
- A materialização Dataform pode ser repetida sem alterar o resultado lógico
  da Silver, desde que o mesmo contrato de origem seja mantido.
- Dataflow Batch grava Bronze append-only com `batch_id`. A Silver deduplica
  por chave de negócio, portanto o resultado analítico é semanticamente
  idempotente. Antes de uma operação de produção com retries após falha
  parcial, deve ser adicionado um registro de lotes ou uma etapa de staging
  para evitar duplicidade física no Bronze.

## Evolução para produção

1. Reativar/provisionar Composer somente quando houver necessidade operacional.
2. Publicar as DAGs pelo workflow manual e validar permissões da service account.
3. Configurar invocação Dataform por release/compilation result aprovado.
4. Implementar controle de lotes Dataflow no destino antes de permitir retries
   automáticos que possam repetir `WRITE_APPEND`.
5. Adicionar alertas de falha, DLQ e SLA no monitoramento do ambiente escolhido;
   a matriz de sinais está em `docs/OBSERVABILITY.md`.
