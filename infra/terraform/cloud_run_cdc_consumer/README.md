# Consumidor CDC no Cloud Run

Este modulo implementa o caminho CDC completo para as 13 tabelas PostgreSQL,
sem criar uma tabela incremental por entidade:

```text
Debezium -> 13 topicos Pub/Sub -> 13 assinaturas push
         -> um servico Cloud Run -> ecommerce_bronze.cdc_events_raw
```

A tabela `cdc_events_raw` e append-only, particionada por `ingested_at` e
clusterizada por `source_table` e `operation`. Ela preserva o evento original
e os metadados necessarios para replay, auditoria e deduplicacao na Silver.

As assinaturas Pull criadas pelo modulo `pubsub_cdc` permanecem existentes.
Isso permite inspeção, replay controlado e troubleshooting sem misturar o
transporte de diagnóstico com o consumidor operacional.

## Recursos administrados

- uma tabela BigQuery `cdc_events_raw`;
- uma service account de runtime do Cloud Run;
- uma service account de autenticação do push Pub/Sub;
- um serviço Cloud Run com endpoint `/pubsub`;
- uma assinatura push por tabela;
- IAM de escrita no dataset, invocação do serviço e emissão de tokens OIDC;
- retry, ordering e encaminhamento para a DLQ existente.

O módulo não executa o Debezium, não altera o PostgreSQL e não cria os tópicos
de origem. Os tópicos devem existir pelo módulo
`infra/terraform/pubsub_cdc`.

## Ordem de implantação

1. Publicar a imagem CDC no Artifact Registry e obter o digest SHA-256.
2. Preencher `consumer_image` no `terraform.tfvars`, sem colocar credenciais.
3. Executar `terraform init`, `fmt`, `validate` e `plan`.
4. Revisar o plano e autorizar explicitamente o `apply`.
5. Configurar o workflow de imagens com o nome do serviço e conceder ao
   deployer `Service Account User` sobre `de-cdc-consumer`.
6. Validar primeiro uma alteração controlada em `categorias` e depois revisar
   métricas, logs e DLQ para as 13 tabelas.

## Validação local do módulo

```powershell
terraform -chdir=infra/terraform/cloud_run_cdc_consumer init
terraform -chdir=infra/terraform/cloud_run_cdc_consumer fmt -check
terraform -chdir=infra/terraform/cloud_run_cdc_consumer validate
```

O `plan` e somente leitura. Não executar `apply` sem revisão e autorização.
