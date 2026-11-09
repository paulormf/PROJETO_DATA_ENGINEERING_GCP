# Workload Identity Federation para deploy das DAGs

## Objetivo

Este modulo configura a identidade usada pelo GitHub Actions para publicar as
DAGs no bucket do Composer sem chave JSON permanente.

O pool `github-actions` ja existia no projeto e e compartilhado com outra
integracao. Por isso o modulo consulta esse pool e cria um provider exclusivo
para este repositorio. O provider existente `github-oidc` nao e alterado.

Recursos administrados por este modulo:

- provider OIDC exclusivo para `paulormf/PROJETO_DATA_ENGINEERING_GCP`;
- service account `de-github-composer-deployer`;
- binding `roles/iam.workloadIdentityUser` entre o repositorio e a service
  account;
- binding de bucket `roles/storage.objectUser` para o bucket de DAGs do
  Composer.

O modulo nao cria nem altera o ambiente Composer e nao modifica o provider ou
a service account de outro repositorio.

## Validacao e plano

Na raiz do repositorio:

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check
terraform validate
terraform plan
```

Revise especialmente o repositorio, o provider WIF, a service account e o
bucket antes de aplicar. O `terraform plan` e somente leitura; `terraform
apply` cria os recursos e bindings listados acima.

## Equivalente no Console

1. IAM e administrador > Identity Federation > selecione o pool existente
   `github-actions`.
2. Crie um provider OIDC com ID `github-data-engineering-gcp`, issuer
   `https://token.actions.githubusercontent.com` e mapeamentos para
   `google.subject`, `attribute.repository` e `attribute.ref`.
3. Restrinja a condicao a
   `assertion.repository == 'paulormf/PROJETO_DATA_ENGINEERING_GCP'` e
   `assertion.ref == 'refs/heads/main'`.
4. Crie a service account `de-github-composer-deployer`.
5. Na permissao da service account, permita que o principal do repositorio do
   pool use `roles/iam.workloadIdentityUser`.
6. No bucket de DAGs do Composer, conceda `Storage Object User` somente para a
   service account de deploy.
7. No GitHub, crie o ambiente `composer-lab` e cadastre as quatro variaveis
   indicadas em `docs/GITHUB_ACTIONS_CI_CD.md`.

O identificador do provider precisa conter o numero do projeto, por exemplo:

`projects/756989253873/locations/global/workloadIdentityPools/github-actions/providers/github-data-engineering-gcp`
