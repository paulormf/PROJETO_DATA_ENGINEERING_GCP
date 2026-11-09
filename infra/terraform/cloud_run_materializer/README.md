# IAM do materializer Bronze - Terraform

Este modulo prepara a identidade e o menor conjunto de permissoes para o
materializer ler Parquets do Cloud Storage e gravar tabelas no BigQuery.

## Recursos declarados

- uma service account dedicada `de-bronze-materializer`;
- `roles/storage.objectViewer` somente no bucket Bronze;
- `roles/bigquery.jobUser` no projeto, para criar jobs BigQuery;
- `roles/bigquery.dataEditor` somente no dataset Bronze, para criar a staging
  e publicar as tabelas de destino.
- um Cloud Run Job usando a imagem publicada por digest.

O modulo nao cria bucket, dataset, imagem, versao de secret ou DAG Composer.
Esses recursos possuem ciclos de vida e autorizacoes proprios. O Job recebe
argumentos fallback validos, mas o Composer devera sobrescrever tabela, run_id
e data de ingestao em cada execucao.

## Validacao sem alteracao GCP

```powershell
terraform -chdir=infra/terraform/cloud_run_materializer fmt -check
terraform -chdir=infra/terraform/cloud_run_materializer init -backend=false
terraform -chdir=infra/terraform/cloud_run_materializer validate
```

Para uma revisao somente leitura com os valores de exemplo:

```powershell
Push-Location infra/terraform/cloud_run_materializer
terraform plan -var-file terraform.tfvars.example
Pop-Location
```

O `apply` fica para uma etapa posterior e somente deve ocorrer com autorizacao
explicita, depois da revisao do dataset, bucket, identidade, digest e
argumentos fallback que serao configurados no Job.

O principal que executar o apply precisa ter `iam.serviceAccounts.actAs` para
a service account do materializer. Essa permissao nao e concedida
automaticamente pelo modulo, evitando ampliar o acesso de usuarios ou de uma
identidade de CI sem uma decisao explicita.

## Console equivalente

1. Criar uma service account dedicada para o materializer.
2. No bucket Bronze, conceder `Storage Object Viewer` somente para essa conta.
3. No projeto, conceder `BigQuery Job User` para essa conta.
4. No dataset `ecommerce_bronze`, conceder `BigQuery Data Editor` somente para
   essa conta.

Nao conceder Owner, Editor, Storage Admin ou BigQuery Admin ao runtime.
