# Cloud Run Job — Full Extract

Imagem do job batch que executa o exportador PostgreSQL -> Cloud Storage.

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

## Build local

Executar na raiz do repositório:

```powershell
docker build -f infra/cloud_run/full_extract/Dockerfile -t ecommerce-full-extract:dev .
```

O build não faz push nem deploy. A execução real dependerá de variáveis de ambiente e segredos fornecidos no runtime.
