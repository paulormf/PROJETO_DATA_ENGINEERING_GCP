# Managed Service for Apache Airflow / Composer

Este modulo prepara o ambiente de orquestracao para a DAG de materializacao
Bronze. Ele declara uma service account dedicada, o papel base do Composer e
permissoes especificas no Cloud Run Job materializer.

## O que o modulo declara

- service account `de-composer-orchestrator`;
- `roles/composer.worker` no projeto;
- `roles/run.jobsExecutorWithOverrides` no Job
  `ecommerce-bronze-materializer`;
- `roles/run.viewer` no mesmo Job, para consultar a execucao e seus estados;
- um ambiente Composer 3 com a imagem escolhida em `image_version`.

O modulo nao cria APIs, rede, VPN, firewall, secrets ou recursos do PostgreSQL.
O Composer desta etapa somente coordena GCS, BigQuery e Cloud Run.

## Custo e operacao

O Composer e o componente de custo continuo desta etapa. A precificacao atual
do Composer 3 em `us-central1` usa DCU-horas; a pagina oficial informa
US$ 0,06 por DCU-hora, alem do armazenamento do banco e eventual transferencia
de rede. Um ambiente que permanecesse em media com 12 DCUs durante 730 horas
representaria aproximadamente US$ 525,60 antes desses adicionais. O valor real
depende do preset, autoscaling, workers e tempo ativo.

Para laboratorio, recomenda-se manter o ambiente pequeno e destrui-lo quando
nao estiver sendo usado. O modo de desenvolvimento do Composer 3 pode ser
hibernado e reduz a maior parte dos custos, mas a documentacao atual informa
que esse modo exige Airflow 3 e nao possui suporte Terraform para a criacao.
Por isso, o modulo representa o caminho padrao Composer 3; o modo de
desenvolvimento e uma alternativa manual pelo Console.

## Validacao sem alterar a GCP

```powershell
terraform -chdir=infra/terraform/composer fmt -check
terraform -chdir=infra/terraform/composer init -backend=false
terraform -chdir=infra/terraform/composer validate
```

O `apply` exige autorizacao explicita. A conta que criar o ambiente precisa
ter permissao para criar ambientes Composer e `iam.serviceAccounts.actAs` na
service account escolhida.

## Equivalente manual pelo Console

### 1. Criar a identidade do Composer

1. Abra **IAM e administrador > Contas de serviço**.
2. Crie `de-composer-orchestrator` no projeto `botbrewpub-ghsurp`.
3. No projeto, conceda **Composer Worker** para essa conta.
4. No Cloud Run > Jobs > `ecommerce-bronze-materializer` > Permissões,
   conceda para a conta:
   - **Cloud Run Jobs Executor With Overrides**;
   - **Cloud Run Viewer**.

As permissões de execução com overrides são necessárias porque a DAG altera os
argumentos `--table`, `--run-id` e `--ingestion-date` por execução. A permissão
`run.jobs.runWithOverrides` é diferente de apenas consultar o Job.

### 2. Criar o ambiente

1. Abra **Composer / Managed Service for Apache Airflow > Environments**.
2. Clique em **Create**.
3. Escolha **Composer 3**, região `us-central1` e a versão exata disponível
   da imagem Airflow 2.11.x.
4. Use a service account `de-composer-orchestrator`.
5. Use o preset **Small**, resiliência padrão e sem rede privada nesta etapa.
   A DAG não acessa o PostgreSQL; ela acessa apenas serviços GCP.
6. Mantenha zero triggerers enquanto a DAG estiver com `deferrable=False`.
7. Restrinja o acesso ao Web Server ao seu IP/CIDR quando a tela oferecer essa
   opção.
8. Adicione labels `environment=lab`, `component=orchestration` e
   `managed_by=console`.
9. Clique em **Create** e aguarde a criação, que pode levar cerca de 25
   minutos.

### 3. Enviar a DAG pelo Console

1. Abra o ambiente criado e localize o link do bucket de ambiente.
2. Entre na pasta `dags/` do Cloud Storage.
3. Envie os arquivos:
   - `orchestration/composer/dags/ecommerce_bronze_materialization.py`;
   - `orchestration/composer/dags/materialization_plan.py`.
4. Aguarde o parser do Airflow identificar a DAG.
5. Abra o Airflow UI pelo ambiente e confirme a DAG
   `ecommerce_bronze_materialization`.

### 4. Disparar manualmente

Na tela da DAG, use **Trigger DAG** e informe o JSON abaixo. O primeiro teste
deve usar o ciclo já validado, sem iniciar uma nova extração:

```json
{
  "project_id": "botbrewpub-ghsurp",
  "region": "us-central1",
  "materializer_job_name": "ecommerce-bronze-materializer",
  "schema": "ecommerce",
  "run_id": "full_20261109_001",
  "ingestion_date": "2026-11-09",
  "bronze_prefix": "bronze/parquet"
}
```

O teste pelo Composer executará novamente a materialização do mesmo ciclo; o
materializer foi desenhado para substituir somente a partição lógica do mesmo
`run_id`, portanto a operação é idempotente.
