# Debezium Server CDC

Esta pasta contem a configuracao local do Debezium Server para o projeto de e-commerce.

## Objetivo atual

Capturar mudancas das 13 tabelas depois de iniciar um ciclo CDC isolado, usando a publicacao `ecommerce_gcp_publication`, o slot `ecommerce_gcp_v2_debezium_slot` e topicos com prefixo `ecommerce_gcp_v2`.

O template usa `snapshot.mode=no_data`: o Debezium nao executa a carga full. A fotografia inicial continua sendo produzida pelo Cloud Run Job em Parquet. Todos os eventos CDC desde o inicio do ciclo sao preservados e reaplicados sobre essa fotografia no destino.

## Estado

- A publicacao PostgreSQL ja foi criada e validada com as 13 tabelas.
- O slot v2 ainda nao foi criado; ele so deve ser criado na inicializacao controlada do novo ciclo.
- Os novos topicos e assinaturas ainda nao foram criados.
- O arquivo `application.properties.example` nao contem credenciais.

## Local de execucao

No laboratorio, o Debezium Server executa neste computador em Docker e acessa o PostgreSQL no outro computador pela rede. O arquivo `.env` permanece local e o diretorio montado `/debezium/data` persiste offsets e historico.

Para producao, o runtime deve ser dedicado e continuamente disponivel. O armazenamento local de offsets e adequado ao laboratorio, mas requer volume persistente, backup e procedimento de recuperacao; uma instancia efemera sem esses controles pode perder continuidade.

## Preparacao local

1. Revisar o template sem substituir o arquivo ativo durante uma execucao.
2. Confirmar os 13 topicos e assinaturas v2 antes de iniciar o conector.
3. Confirmar as credenciais ADC locais usadas pelo container.
4. Preservar o diretorio atual de offsets; nao o reutilizar no ciclo v2.
5. Copiar o template aprovado para `application.properties`.
6. Iniciar uma unica instancia com `docker compose -f infra/local/docker-compose.yml up -d debezium-server`.
7. Validar o streaming sem snapshot de dados e registrar o LSN inicial do ciclo.

O arquivo preenchido, o `.env` e o diretorio `data/` nao devem ser versionados.

## Criterios de aceite

- Debezium inicia sem criar ou alterar a publicacao existente.
- O slot `ecommerce_gcp_v2_debezium_slot` e criado pelo Debezium.
- Nenhum evento `op=r` de snapshot e gerado pelo ciclo v2.
- As 13 tabelas estao incluidas e possuem topico isolado.
- Eventos controlados de insert, update e delete chegam ao Pub/Sub.
- O offset persiste depois de uma reinicializacao controlada.
- O LSN inicial e o identificador do ciclo sao registrados antes do novo full.

O procedimento de corte e a regra de materializacao estao em `../../docs/CDC_FULL_COORDINATION.md`.
