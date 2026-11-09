# CI/CD das DAGs do Composer

## Objetivo

Este repositório separa validação de código e publicação no Composer:

- `ci.yml` executa testes Python e valida a sintaxe das DAGs;
- `deploy-composer-dags.yml` publica os dois arquivos necessários para a DAG
  Bronze no bucket do ambiente Composer;
- a publicação ocorre usando Workload Identity Federation, sem chave JSON de
  service account;
- o deploy é executado automaticamente após push/merge em `main` quando houver
  alteração nas DAGs, e também está disponível por `workflow_dispatch`;
- o ambiente GitHub `composer-lab` pode exigir aprovação antes do deploy.

## Arquivos publicados

O workflow publica os arquivos abaixo em `gs://<bucket>/dags/`:

- `orchestration/composer/dags/ecommerce_bronze_materialization.py`;
- `orchestration/composer/dags/materialization_plan.py`.

O segundo arquivo é um módulo auxiliar importado pela DAG. Ele não aparece
como DAG separado na interface do Airflow, mas precisa estar no mesmo
diretório do bucket para que o import funcione.

## Variáveis do ambiente GitHub

Criar um ambiente GitHub chamado `composer-lab`. As variáveis abaixo devem ser
configuradas no ambiente, e não como valores no YAML:

| Variável | Finalidade |
| --- | --- |
| `GCP_PROJECT_ID` | ID do projeto GCP, atualmente `botbrewpub-ghsurp` |
| `GCP_WIF_PROVIDER` | Identificador completo do provider WIF |
| `GCP_DEPLOYER_SERVICE_ACCOUNT` | Service account dedicada ao deploy |
| `COMPOSER_DAGS_BUCKET` | Bucket de DAGs do Composer, sem `gs://` |

Esses valores não são senhas, mas ficam fora do código para permitir separar
laboratório, homologação e produção sem alterar o workflow.

## Execução

1. Fazer merge de uma alteração aprovada em `main`; o workflow será disparado
   automaticamente quando a alteração atingir os caminhos das DAGs.
2. Para uma execução manual, abrir GitHub > Actions > `Deploy Composer DAGs` e
   selecionar `Run workflow`.
3. Conferir o log de autenticação e os dois objetos publicados.
4. Aguardar a sincronização e o parsing do Composer.
5. Verificar no Airflow a aba `Code` da DAG e, se aplicável, executar uma
   rodada de validação.

O workflow não executa a DAG, não inicia o Cloud Run Job e não materializa
tabelas. Ele somente publica o código versionado no bucket do Composer.

## Segurança e operação

- O job usa `id-token: write` apenas para obter o token OIDC efêmero do GitHub.
- O service account do deploy deve ter somente as permissões necessárias para
  escrever os objetos do bucket de DAGs.
- O provider WIF deve restringir o repositório e, quando possível, a branch e
  o ambiente GitHub.
- O workflow não usa `credentials_json`, chave privada ou segredo de banco.
- Para produção, o ambiente GitHub deve exigir aprovação antes do deploy.

## Limitações conhecidas desta primeira versão

Esta versão publica os dois arquivos conhecidos da DAG. Ela não remove
automaticamente DAGs obsoletas do bucket. A remoção deve ser uma mudança
explícita e revisada, evitando apagar DAGs de outros fluxos do ambiente.

O Composer sincroniza o bucket com os componentes do Airflow com atraso. Uma
publicação bem-sucedida no GitHub Actions significa que os objetos chegaram ao
GCS; a confirmação operacional é a DAG aparecer com o código atualizado e
sem erro de import no Airflow.
