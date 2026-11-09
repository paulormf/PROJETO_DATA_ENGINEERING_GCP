# Orquestracao Composer

## Escopo desta etapa

`ecommerce_bronze_materialization.py` orquestra a materializacao do ciclo
full ja publicado no Cloud Storage:

1. monta em runtime os argumentos do ciclo (`run_id`, data e schema);
2. cria uma tarefa mapeada por tabela;
3. executa o mesmo Cloud Run Job `ecommerce-bronze-materializer` para cada
   tabela;
4. limita a quatro materializacoes simultaneas;
5. deixa o Airflow registrar sucesso, falha e retry por tabela.

O Job Cloud Run e um recurso unico. As 13 tarefas sao execucoes independentes
do mesmo Job, e nao 13 Jobs permanentes. Isso permite reprocessar somente uma
tabela sem repetir as demais.

Esta DAG nao cria recursos GCP, nao inicia o Debezium e nao executa CDC. Ela
materializa somente um `run_id` full coordenado que ja possui manifestos
`status=succeeded` no GCS. A reconciliacao full + CDC continua sendo uma etapa
posterior.

## Estrutura enviada ao Composer

O bucket de ambiente do Composer deve receber estes dois arquivos no mesmo
diretorio `dags/`:

- `ecommerce_bronze_materialization.py`;
- `materialization_plan.py`.

O teste `tests/unit/test_materialization_plan.py` garante que a lista de
tabelas publicada na DAG nao divergiu de `config/ingestion_tables.json`.

## Parametros de uma execucao

Ao disparar manualmente a DAG, informe `run_id` e `ingestion_date` do mesmo
manifesto coordenado. Os valores default reproduzem o ciclo validado em
2026-11-09. Em um ambiente real, o coordenador do ciclo devera gerar esses
valores e passa-los via `dag_run.conf`, em vez de depender dos defaults.

Exemplo de configuracao de execucao:

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

## Dependencia do Composer

O ambiente precisa ter o provider Google do Airflow com
`CloudRunExecuteJobOperator`. Para execucoes longas, a versao operacional
deve ser validada contra a imagem do Composer escolhida. O DAG inicia com
`deferrable=False` para nao assumir a existencia de um triggerer no ambiente;
depois de habilitar e validar triggerer, essa decisao pode ser alterada para
liberar slots de worker durante o polling.

O service account do Composer precisa ter permissao para executar o Job Cloud
Run. Essa permissao e distinta da service account runtime do materializer e
deve ser concedida pelo modulo IAM do Composer em uma etapa especifica.

## Validacao local

Na raiz do repositorio:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/unit/test_materialization_plan.py -q
& .\.venv\Scripts\python.exe -c "import ast, pathlib; [ast.parse(p.read_text(encoding='utf-8')) for p in pathlib.Path('orchestration/composer/dags').glob('*.py')]; print('DAG syntax OK')"
```

Esses comandos nao importam Airflow, nao fazem upload para Composer e nao
executam Cloud Run.
