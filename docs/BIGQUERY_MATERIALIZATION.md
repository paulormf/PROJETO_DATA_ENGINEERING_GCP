# Materializacao GCS -> BigQuery

## Decisao

A copia fisica dos Parquets do Cloud Storage para o BigQuery sera executada
por um job Python de materializacao, e nao por Dataform.

O componente esta em
`src/materialization/bigquery_full_materializer.py` e trabalha uma tabela por
execucao. O desenho permite que o Composer crie uma tarefa por tabela e
controle dependencias, retries, timeout e alertas.

## Fluxo

1. montar o caminho do `manifest.json` a partir de bucket, schema, tabela e
   `run_id`;
2. rejeitar manifestos incompletos, de outra tabela ou
   `cdc_coordination.status != coordinated`;
3. carregar explicitamente as partes Parquet listadas no manifesto para uma
   tabela staging deterministica;
4. comparar `COUNT(*)` do staging com `manifest.rows`;
5. criar a tabela destino se necessario, por padrao `bronze_<tabela>`, particionada por
   `_ingestion_date` e clusterizada pela chave primaria;
6. substituir, em uma transacao BigQuery, somente as linhas do mesmo
   `_ingestion_run_id`;
7. validar a contagem publicada e remover o staging somente apos sucesso.

O job nao executa regras de negocio, nao remove nulos e nao transforma o
modelo de origem. A Bronze preserva o snapshot e adiciona metadados de
linhagem, incluindo `run_id`, `epoch_id`, `start_lsn`, schema, tabela e data
de ingestao.

O nome da tabela destino pode ser informado explicitamente pelo orquestrador
com `--target-table`. Isso evita colisao com tabelas legadas ou com nomes
mantidos por contratos existentes. A tabela manual
`ecommerce_bronze.categorias_raw` nao sera sobrescrita pelo padrao
`bronze_categorias`.

## Papel do Dataform

Dataform deve começar depois que a Bronze estiver materializada. Ele será
responsavel por:

- modelos Silver SQLX;
- limpeza e padronizacao;
- deduplicacao e aplicacao do estado CDC;
- dimensoes, fatos e Data Marts Gold;
- assertions, dependencias, documentacao e execucoes incrementais.

Usar Dataform para controlar diretamente a leitura dos manifests e a carga
GCS -> BigQuery misturaria transporte, controle operacional e transformacao
SQL. Uma excecao possivel seria um `operations` SQLX para um caso simples,
mas nao sera a estrategia principal deste projeto.

## Operacao futura

O Cloud Composer devera disparar o job de materializacao depois que o full
coordenado for concluido. Depois da reconciliacao com o CDC persistido, o DAG
acionara o workflow Dataform para Silver e Gold.

O dataset `ecommerce_bronze` ja existe no projeto e possui a tabela manual de
validacao `categorias_raw`, com 100 registros. O novo materializer ainda nao
foi executado e nao deve sobrescrever essa tabela sem uma migracao controlada,
pois ela nao possui os metadados de linhagem previstos neste contrato. A
imagem local do materializer foi validada com `docker build` e `--help`, mas
ainda nao foi publicada no Artifact Registry. O Job Cloud Run e o DAG Composer
ainda nao foram criados; esses recursos exigem uma etapa posterior de
Terraform/Console e autorizacao explicita para apply/deploy.
