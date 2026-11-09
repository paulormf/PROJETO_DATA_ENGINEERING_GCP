# Dataform e datasets analiticos - Terraform

Este modulo prepara a fundacao cloud para o projeto Dataform:

- dataset `ecommerce_silver` na mesma localizacao do Bronze;
- dataset `ecommerce_dataform_assertions` para resultados de qualidade;
- service account dedicada `de-dataform-runner`;
- acesso de leitura ao dataset Bronze;
- acesso de escrita somente aos datasets Silver e de assertions;
- permissao `BigQuery Job User` no projeto;
- permissao explicita do Dataform service agent para impersonar a service
  account de execucao;
- repositorio Dataform regional e seu vinculo Developer Connect.

O repositorio nao recebe token, senha ou chave do GitHub. A integracao com o
Git remoto usa Developer Connect e e declarada no bloco
`git_remote_settings`, por meio das variaveis `dataform_git_repository_url`,
`dataform_git_repository_link` e `dataform_git_default_branch`. Assim, o
Terraform deste modulo nao cria credenciais nem as grava no state.

## Localizacao

`bigquery_location` deve ser a localizacao efetiva dos datasets BigQuery. O
`dataform_region` e a regiao do repositorio Dataform; eles podem ser
diferentes, mas o `defaultLocation` em `workflow_settings.yaml` deve
corresponder a localizacao dos datasets de processamento.

Neste projeto, a consulta de leitura confirmou `ecommerce_bronze` em
`us-central1`; por isso o exemplo usa `us-central1` para os novos datasets.

## Fluxo seguro

1. Copiar `terraform.tfvars.example` para `terraform.tfvars`.
2. Revisar IDs, localizacao e identificador Developer Connect, sem inserir
   credenciais.
3. Executar `terraform fmt`.
4. Executar `terraform init`.
5. Executar `terraform validate`.
6. Executar `terraform plan` e revisar os recursos.
7. Somente apos aprovacao explicita executar `terraform apply`.

O `plan` e seguro e nao cria recursos. Em um ambiente vazio, o `apply` cria
os dois datasets, a service account, IAM e o repositorio Dataform. Neste
projeto o repositorio novo foi criado no console e importado no state; o
proximo apply deve apenas alinhar metadados e a service account.

## Equivalente no Console

1. BigQuery: criar os datasets `ecommerce_silver` e
   `ecommerce_dataform_assertions`, ambos em `us-central1`.
2. IAM: criar `de-dataform-runner`.
3. Conceder `BigQuery Data Viewer` no dataset Bronze, `BigQuery Data Editor`
   nos dois datasets novos e `BigQuery Job User` no projeto.
4. Na service account, adicionar o Dataform service agent com `Service
   Account User` e `Service Account Token Creator`.
5. Developer Connect: conectar o repositorio GitHub ao projeto.
6. Dataform: criar `ecommerce-dataform-gcp` em `us-central1`, usando a
   service account criada e o vinculo Developer Connect.

Esses passos manuais representam o que o Terraform declara; nao devem ser
executados junto com um `apply` sem antes decidir qual sera a fonte de
verdade, para evitar recursos duplicados ou drift.
