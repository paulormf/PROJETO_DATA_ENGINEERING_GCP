# Dataform e datasets analiticos — Terraform

Este modulo prepara a fundacao cloud para o projeto Dataform:

- dataset `ecommerce_silver` na mesma localizacao do Bronze;
- dataset `ecommerce_dataform_assertions` para resultados de qualidade;
- service account dedicada `de-dataform-runner`;
- acesso de leitura ao dataset Bronze;
- acesso de escrita somente aos datasets Silver e de assertions;
- permissao `BigQuery Job User` no projeto;
- permissao explicita do Dataform service agent para impersonar a service
  account de execucao;
- repositorio Dataform regional.

O repositorio nao recebe token, senha ou chave do GitHub. A integracao com o
Git remoto sera configurada em uma etapa posterior usando Secret Manager ou
Developer Connect, conforme a estrategia de CI/CD aprovada. Assim, o
Terraform deste modulo nao cria credenciais nem as grava no state.

## Localizacao

`bigquery_location` deve ser a localizacao efetiva dos datasets BigQuery. O
`dataform_region` e a regiao do repositorio Dataform; eles podem ser
diferentes, mas o `defaultLocation` em `dataform/workflow_settings.yaml` deve
corresponder a localizacao dos datasets de processamento.

Neste projeto, a consulta de leitura confirmou `ecommerce_bronze` em
`us-central1`; por isso o exemplo usa `us-central1` para os novos datasets.

## Fluxo seguro

1. Copiar `terraform.tfvars.example` para `terraform.tfvars`.
2. Revisar IDs e localizacao, sem inserir credenciais.
3. Executar `terraform fmt`.
4. Executar `terraform init`.
5. Executar `terraform validate`.
6. Executar `terraform plan` e revisar os recursos.
7. Somente apos aprovacao explicita executar `terraform apply`.

O `plan` e seguro e nao cria recursos. O `apply` criara dois datasets vazios,
uma service account, IAM e um repositorio Dataform. A criacao do repositorio
nao executa o workflow nem materializa tabelas.

## Equivalente no Console

1. BigQuery → criar os datasets `ecommerce_silver` e
   `ecommerce_dataform_assertions`, ambos em `us-central1`.
2. IAM e administrador → Service Accounts → criar `de-dataform-runner`.
3. Conceder `BigQuery Data Viewer` no dataset Bronze, `BigQuery Data Editor`
   nos dois datasets novos e `BigQuery Job User` no projeto.
4. IAM da service account → adicionar o Dataform service agent com
   `Service Account User` e `Service Account Token Creator`.
5. Dataform → Create repository → informar `ecommerce-dataform`, regiao
   `us-central1` e a service account criada.

Esses passos manuais representam o que o Terraform declarara; nao devem ser
executados junto com um `apply` sem antes decidir qual sera a fonte de verdade,
para evitar recursos duplicados ou drift.
