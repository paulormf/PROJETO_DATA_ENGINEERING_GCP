# Workload Identity Federation para imagens Cloud Run

## Objetivo

Este modulo cria a identidade usada pelo GitHub Actions para publicar as
imagens `ecommerce-full-extract`, `ecommerce-bronze-materializer` e
`ecommerce-cdc-consumer`, atualizar os Jobs Cloud Run existentes e atualizar o
servico Cloud Run do consumidor por digest imutavel.

O modulo reutiliza o pool WIF e o provider exclusivos deste repositorio, mas
cria uma service account separada da identidade de deploy das DAGs. Isso
mantem menor privilegio e permite controlar os deployments de Composer e Cloud
Run separadamente.

## Recursos administrados

- service account `de-github-cloud-run-deployer`;
- binding `roles/iam.workloadIdentityUser` para o repositorio GitHub;
- `roles/artifactregistry.writer` somente no repositorio de imagens;
- `roles/run.developer` no projeto para atualizar Jobs Cloud Run;
- `roles/iam.serviceAccountUser` somente nas service accounts de runtime dos
  Jobs e do consumidor CDC.

O modulo nao cria, executa ou exclui Jobs Cloud Run. O workflow publica a
imagem e atualiza somente a referencia de imagem do Job, preservando os
argumentos, variaveis e segredos ja configurados. Cada service account de
runtime, incluindo `de-api-extract-writer`, recebe `roles/iam.serviceAccountUser`
somente para o deployer.

## Validacao

Na raiz do repositorio:

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check
terraform validate
terraform plan
```

O `plan` e somente leitura. O `apply` exige autorizacao explicita e cria a
service account e os bindings listados acima.

## Equivalente no Console

1. Crie a service account `de-github-cloud-run-deployer`.
2. Na service account, permita o principal do repositorio do pool WIF usando
   `Workload Identity User`.
3. No repositorio `data-engineering` do Artifact Registry, conceda
   `Artifact Registry Writer` somente para essa service account.
4. No projeto, conceda `Cloud Run Developer` para essa service account.
5. Nas service accounts `de-ingestion-writer`, `de-bronze-materializer` e
   `de-api-extract-writer`, conceda `Service Account User` para a identidade
   de deploy.
6. No ambiente GitHub `cloud-run-lab`, cadastre as variaveis emitidas pelo
   output `github_environment_variables`.
