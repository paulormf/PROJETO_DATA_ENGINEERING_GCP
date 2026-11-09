# IAM do materializer Bronze - Terraform

Este modulo prepara a identidade e o menor conjunto de permissoes para o
materializer ler Parquets do Cloud Storage e gravar tabelas no BigQuery.

## Recursos declarados

- uma service account dedicada `de-bronze-materializer`;
- `roles/storage.objectViewer` somente no bucket Bronze;
- `roles/bigquery.jobUser` no projeto, para criar jobs BigQuery;
- `roles/bigquery.dataEditor` somente no dataset Bronze, para criar a staging
  e publicar as tabelas de destino.

O modulo nao cria bucket, dataset, imagem, versao de secret, Cloud Run Job ou
DAG Composer. Esses recursos possuem ciclos de vida e autorizacoes proprios.
O Cloud Run Job sera definido depois que a imagem estiver publicada por digest
e o contrato de overrides do Composer estiver validado.

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
explicita, depois da revisao do dataset, bucket e identidade que receberao as
permissoes.

## Console equivalente

1. Criar uma service account dedicada para o materializer.
2. No bucket Bronze, conceder `Storage Object Viewer` somente para essa conta.
3. No projeto, conceder `BigQuery Job User` para essa conta.
4. No dataset `ecommerce_bronze`, conceder `BigQuery Data Editor` somente para
   essa conta.

Nao conceder Owner, Editor, Storage Admin ou BigQuery Admin ao runtime.
