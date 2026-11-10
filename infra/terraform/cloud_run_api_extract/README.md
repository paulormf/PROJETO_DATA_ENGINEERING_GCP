# Cloud Run API Extract

Este modulo cria o Cloud Run Job que extrai a API publica DummyJSON e grava o
envelope Raw no bucket Bronze.

## Recursos

- service account dedicada `de-api-extract-writer`;
- `roles/storage.objectCreator` somente no bucket Bronze;
- `roles/logging.logWriter` para logs da execucao;
- Cloud Run Job com imagem referenciada por digest imutavel.

O modulo nao cria bucket, imagem, dataset ou API key. A imagem e publicada
pelo workflow de CI/CD e o digest e aplicado pelo Terraform ou atualizado pelo
workflow, sem executar o Job automaticamente.

O `object_name` fallback existe apenas para validar a configuracao inicial.
Em uma execucao real, o Composer ou outro orquestrador deve fornecer um
caminho unico por execucao.

## Validacao

```powershell
terraform -chdir=infra/terraform/cloud_run_api_extract fmt -check
terraform -chdir=infra/terraform/cloud_run_api_extract init -backend=false
terraform -chdir=infra/terraform/cloud_run_api_extract validate
```

Antes de `apply`, substituir o digest e revisar os argumentos. O principal que
executar o `apply` precisa ter `iam.serviceAccounts.actAs` para a identidade do
Job.
