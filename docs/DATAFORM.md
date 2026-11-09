# Dataform

O projeto Dataform deste repositorio fica na raiz do monorepo para que o mesmo
Pull Request possa revisar codigo Python, DAGs, infraestrutura e modelos SQL.

## Estrutura

- `workflow_settings.yaml`: projeto, regiao e datasets padrao do Dataform;
- `includes/table_catalog.js`: catalogo das tabelas de origem e chaves primarias;
- `definitions/sources.js`: declaracoes das tabelas Bronze e do raw CDC;
- `definitions/silver_tables.js`: modelos incrementais Silver reconciliando o
  baseline full e os eventos Debezium;
- `definitions/silver_assertions.js`: assertions de integridade de chaves;
- `infra/terraform/dataform/`: datasets, IAM e repositorio Dataform.

## Validacao local

A validacao de CI executa apenas a compilacao do grafo, sem executar consultas
no BigQuery. A compilacao pode ser reproduzida localmente com Node.js 22 e
Dataform CLI 3.0.50, ou pelo container utilizado no bootstrap inicial.

O primeiro ciclo cloud deve ser executado somente depois de revisar o grafo
compilado e confirmar que as tabelas Bronze e `cdc_events_raw` estao
disponiveis.

## Repositorio Git

O repositorio GCP Dataform deste projeto deve ser separado do repositorio
Dataform legado `ecommerce-dataform`, que pertence ao projeto anterior. O novo
repositorio sera conectado ao repositorio GitHub
`paulormf/PROJETO_DATA_ENGINEERING_GCP` por Developer Connect.
