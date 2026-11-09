# Cloud Run Job - BigQuery Materializer

Imagem do job batch que materializa uma tabela full coordenada do Cloud
Storage em uma tabela Bronze do BigQuery.

## Responsabilidade

O container nao extrai dados do PostgreSQL e nao executa transformacoes
Silver/Gold. Ele:

1. le o manifesto coordenado no Cloud Storage;
2. carrega as partes Parquet em uma tabela staging;
3. valida a contagem declarada no manifesto;
4. publica somente o `run_id` solicitado na tabela Bronze;
5. remove a staging somente depois da validacao final.

O Dataform continuara responsavel pelas transformacoes SQLX posteriores.

## Configuracao em runtime

O job recebe os parametros de identificacao da execucao. Os argumentos
`--project-id`, `--bucket` e `--dataset` tambem podem ser obtidos das
variaveis `GCP_PROJECT_ID`, `GCS_BUCKET` e `BQ_BRONZE_DATASET`.

Exemplo conceitual para uma tabela:

```text
--schema ecommerce --table categorias --target-table bronze_categorias
--run-id full_20261109_001 --ingestion-date 2026-11-09
```

O `run_id` e a data devem corresponder ao manifesto coordenado publicado no
Cloud Storage. Em operacao, o Composer devera fornecer esses valores por
override da execucao; eles nao devem ficar fixos em uma imagem.

## IAM minimo

A service account do job precisa de:

- `roles/storage.objectViewer` no bucket Bronze;
- `roles/bigquery.jobUser` no projeto;
- `roles/bigquery.dataEditor` somente no dataset Bronze.

O modulo Terraform correspondente prepara essa identidade e essas
permissoes, mas nao cria versoes de secrets nem aplica alteracoes sozinho.

A imagem usa `requirements-materializer.txt`, separado das dependencias de
PostgreSQL, Parquet local e Pub/Sub. Isso reduz o artefato e o tempo de
inicializacao do job sem misturar responsabilidades.

## Build local

Na raiz do repositorio:

```powershell
docker build -f infra/cloud_run/materializer/Dockerfile -t ecommerce-bronze-materializer:dev .
docker run --rm ecommerce-bronze-materializer:dev --help
```

Os comandos acima apenas constroem e validam a imagem local. Nao fazem push,
deploy ou carga no BigQuery.
