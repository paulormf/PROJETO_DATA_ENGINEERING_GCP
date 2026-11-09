# Cloud Run Job — Full Extract

Imagem do job batch que executa o full extract PostgreSQL -> Cloud Storage.

## Configuração em runtime

Obrigatórias:

- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `GCP_PROJECT_ID`
- `GCS_BUCKET`

Opcional:

- `GCS_BRONZE_PREFIX`, padrão `bronze/parquet`;
- `POSTGRES_DBNAME`, padrão `appdb`.

No Cloud Run, credenciais devem ser injetadas pelo Secret Manager. O arquivo `.env` não deve fazer parte da imagem.

O catalogo `config/ingestion_tables.json` e incorporado a imagem. O job pode processar uma tabela especifica ou todas as tabelas do catalogo.

Exemplos de argumentos:

```text
--table categorias --run-id full_20261107_001
--run-id full_20261107_001
--run-id full_20261109_001 --cdc-epoch-id epoch_20261109_001 --cdc-start-lsn HEX/HEX
```

O `run_id` identifica a execucao. O `batch_id` e derivado de `run_id`, schema e tabela. A data de ingestao e derivada da data presente no `run_id` gerado; para um `run_id` manual sem data, informe `--ingestion-date` e reutilize exatamente a mesma data em qualquer repeticao.

Para uma carga coordenada com CDC, `--cdc-epoch-id` e `--cdc-start-lsn` devem ser informados juntos. O LSN e convertido para inteiro e gravado no manifesto para comparacao com `source.lsn` do Debezium. Sem esses argumentos, o manifesto e marcado como `uncoordinated` e serve para laboratorio ou backfill, nao para materializacao full+CDC certificada.

Cada parte e gravada como um objeto Parquet separado; o `checkpoint.json` guarda apenas o estado compacto e o `manifest.json` e publicado com `status=succeeded` ao concluir. O job cria `execution.lock` por lote para impedir duas execucoes concorrentes.

Uma falha interrompida nao e retomada no mesmo prefixo: a transacao PostgreSQL da nova tentativa teria um snapshot diferente e poderia misturar estados da origem. Inicie um novo `run_id`; partes sem manifesto de sucesso sao incompletas e nao podem ser consumidas. Isso repete a leitura daquela tabela e deixa o prefixo incompleto para retencao/lifecycle. Um `execution.lock` abandonado e um sinal para verificar a execucao anterior; nunca o remova enquanto ela puder estar ativa. Uma nova tentativa com outro `run_id` usa outro prefixo.

## Build local

Executar na raiz do repositório:

```powershell
docker build -f infra/cloud_run/full_extract/Dockerfile -t ecommerce-full-extract:dev .
```

O build não faz push nem deploy. A execução real dependerá de variáveis de ambiente e segredos fornecidos no runtime.
