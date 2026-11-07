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
```

O `run_id` identifica a execucao. O `batch_id` e derivado de `run_id`, schema e tabela, tornando retries idempotentes. Cada parte e gravada como um objeto Parquet separado e acompanhada por `checkpoint.json`; o `manifest.json` so e publicado com `status=succeeded`.

Em caso de falha, uma nova execucao com o mesmo `run_id` reutiliza partes concluidas quando os metadados de checkpoint estiverem presentes. O job nao deve ser executado simultaneamente com o mesmo `run_id` para a mesma tabela.

## Build local

Executar na raiz do repositório:

```powershell
docker build -f infra/cloud_run/full_extract/Dockerfile -t ecommerce-full-extract:dev .
```

O build não faz push nem deploy. A execução real dependerá de variáveis de ambiente e segredos fornecidos no runtime.
