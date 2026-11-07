# Secret Manager — Cloud Run Full Extract

Este modulo declara os containers de Secret Manager e o IAM minimo para que o Cloud Run Job leia as credenciais PostgreSQL.

## O que o Terraform cria

- tres recursos `google_secret_manager_secret` sem valores: host, usuario e senha;
- acesso `roles/secretmanager.secretAccessor` somente para a service account informada;
- nenhum `google_secret_manager_secret_version`.

A ausencia de `secret_version` e intencional: valores de usuario e senha nao devem ser escritos no Terraform state, em arquivos `.tfvars` ou em commits.

## Ordem de operacao

1. Copiar `terraform.tfvars.example` para `terraform.tfvars`.
2. Executar `terraform init` e `terraform validate`.
3. Revisar `terraform plan`.
4. Aplicar somente apos aprovacao explicita.
5. Criar os valores dos secrets pelo Console ou por fluxo seguro de administracao.
6. Criar uma versao do secret e testar o acesso com a identidade do Job.

## Console

No Secret Manager, criar os secrets com os IDs definidos no `terraform.tfvars` e adicionar as versoes manualmente. Em cada secret, conceder `Secret Manager Secret Accessor` somente para:

`de-ingestion-writer@botbrewpub-ghsurp.iam.gserviceaccount.com`

Nao conceder acesso publico nem usar chaves JSON.
