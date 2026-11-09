# CI/CD das imagens Cloud Run

## Fluxo

O workflow [deploy-cloud-run-images.yml](../.github/workflows/deploy-cloud-run-images.yml)
executa depois de um push em `main` que altere codigo, dependencias,
Dockerfiles ou o proprio workflow.

1. autentica no GCP por Workload Identity Federation;
2. configura o Docker para o Artifact Registry;
3. constroi `ecommerce-full-extract`, `ecommerce-bronze-materializer` e
   `ecommerce-cdc-consumer`;
4. publica cada imagem com a tag imutavel do commit Git;
5. obtem o digest produzido pelo registry;
6. atualiza os dois Jobs Cloud Run e, quando configurado, o servico CDC para
   esse digest;
7. consulta novamente os workloads e falha se o digest esperado nao estiver
   ativo.

O workflow nao executa os Jobs automaticamente. A execucao continua sendo
disparada pelo Composer ou manualmente, com os argumentos de negocio corretos.

## Separacao de responsabilidades

- Terraform: IAM, service accounts, permissoes do Artifact Registry e
  configuracao estrutural dos Jobs.
- GitHub Actions: build, publicacao do artefato e rollout da imagem.
- Composer: orquestracao das execucoes e argumentos por tabela/run.

O Job full extract existente nao foi recriado nem importado automaticamente
para o Terraform. O workflow atualiza somente sua imagem, preservando a
configuracao de runtime existente.

## Variaveis do ambiente GitHub

Crie o ambiente `cloud-run-lab` e configure como variaveis, nao como secrets,
os valores nao sensiveis emitidos pelo modulo Terraform
`infra/terraform/github_actions_cloud_run`:

- `GCP_PROJECT_ID`;
- `GCP_WIF_PROVIDER`;
- `GCP_DEPLOYER_SERVICE_ACCOUNT`;
- `ARTIFACT_REGISTRY_LOCATION`;
- `ARTIFACT_REGISTRY_REPOSITORY`;
- `CLOUD_RUN_REGION`;
- `FULL_EXTRACT_JOB_NAME`;
- `MATERIALIZER_JOB_NAME`.
- `CDC_CONSUMER_SERVICE_NAME`, depois que o servico CDC for criado pelo
  Terraform.

Nenhum token, senha ou chave privada e utilizado no workflow.

## Rollback

Cada commit gera um digest independente. Para rollback, selecione um digest
anterior conhecido e atualize o Job ou o servico CDC por uma mudanca controlada
no pipeline ou por um procedimento operacional documentado. Nao reutilize a
tag `latest`.
