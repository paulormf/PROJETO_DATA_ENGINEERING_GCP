# Project Status

## Objetivo

Construir uma plataforma de Engenharia de Dados na GCP para o domínio de e-commerce, usando PostgreSQL como origem, arquitetura Medallion, BigQuery, Dataform, Cloud Composer, Debezium, Pub/Sub, observabilidade, qualidade de dados e CI/CD.

## Status atual

### Exportador PostgreSQL para Parquet local

### CorreÃ§Ã£o sobre contagem de `pedidos`

A diferenÃ§a entre `999559` na consulta de tamanho fÃ­sico e `1000000` na exportaÃ§Ã£o nÃ£o foi interpretada como inserÃ§Ã£o durante o processo. A exportaÃ§Ã£o executou a leitura dos registros; a consulta fÃ­sica anterior utilizou uma estimativa do PostgreSQL, que pode estar desatualizada. A contagem exata deve ser feita com `COUNT(*)` e comparada com a contagem do Parquet.

### Validador local de Parquet

### ConfiguraÃ§Ã£o Terraform do Cloud Storage

`terraform plan` executado em 2026-11-07 com `terraform.tfvars` preenchido. Plano observado: `3 to add, 0 to change, 0 to destroy`. Recursos planejados: bucket `botbrewpub-ghsurp-projeto-data-engineering-gcp`, service account `de-ingestion-writer` e binding `roles/storage.objectCreator` no bucket. O plano nÃ£o foi aplicado.

`terraform apply` executado e aprovado pelo usuario em 2026-11-07. Resultado: `3 added, 0 changed, 0 destroyed`. VerificaÃ§Ã£o posterior confirmou os trÃªs recursos no state Terraform. O bucket foi consultado via gcloud e estÃ¡ em `US-CENTRAL1`, classe `STANDARD`, com acesso uniforme habilitado, prevenÃ§Ã£o de acesso pÃºblico aplicada e soft delete efetivo por 7 dias. Nenhuma chave privada foi criada.

Foi implementado `src/ingestion/gcs_uploader.py` para upload de datasets locais validados. O uploader usa ADC, precondiÃ§Ã£o `if_generation_match=0`, nomes de objetos determinÃ­sticos, manifesto enviado por Ãºltimo e verificaÃ§Ã£o de tamanho/MD5 em reexecuÃ§Ãµes. Testes unitÃ¡rios adicionados em `tests/unit/test_gcs_uploader.py`. ValidaÃ§Ã£o: `25 passed in 1.44s`; sem erros no diagnÃ³stico do editor. Nenhum objeto foi enviado ainda.

CorreÃ§Ã£o realizada apÃ³s a primeira tentativa do comando: a opÃ§Ã£o CLI `--bucket` nÃ£o era mapeada para o parÃ¢metro `bucket_name`, causando `TypeError` antes da autenticaÃ§Ã£o e do upload. O parser foi corrigido e o teste de regressÃ£o passou. ValidaÃ§Ã£o atual do uploader: `5 passed`; nenhum objeto foi criado pela tentativa com erro.

Upload real executado em 2026-11-07 para `ecommerce.categorias`. Foram enviados 2 objetos para o bucket Bronze: um Parquet de 3336 bytes e o manifesto de 343 bytes, totalizando 100 linhas. O prefixo inclui origem, schema, tabela, data de ingestÃ£o e batch_id. A confirmaÃ§Ã£o do upload ocorreu somente apÃ³s a gravaÃ§Ã£o de cada objeto; nenhuma mensagem Pub/Sub foi confirmada.

Foi criado `src/ingestion/postgres_gcs_exporter.py` para o caminho de produÃ§Ã£o: PostgreSQL -> Parquet diretamente em um objeto GCS, sem arquivo Parquet intermediÃ¡rio local. A conexÃ£o usa cursor server-side, transaÃ§Ã£o somente leitura, `ParquetWriter` com Snappy e manifesto enviado somente apÃ³s o fechamento do Parquet. Testes em `tests/unit/test_postgres_gcs_exporter.py`: `9 passed` no conjunto focado; diagnÃ³stico do editor sem erros. A exportaÃ§Ã£o direta real ainda nÃ£o foi executada.

CorreÃ§Ã£o realizada apÃ³s a tentativa do exportador direto: a opÃ§Ã£o `--bucket` nÃ£o era mapeada para `bucket_name`, causando `TypeError` antes da conexÃ£o. O parser foi corrigido e o teste de regressÃ£o passou. ValidaÃ§Ã£o atual: `3 passed`; nenhum objeto foi criado pela tentativa com erro.

O exportador direto foi ajustado para gerar os nomes dos objetos automaticamente. A CLI agora recebe `--bronze-prefix` e aceita `--ingestion-date` e `--batch-id` opcionais; `parquet-object` e `manifest-object` nÃ£o precisam mais ser informados manualmente. Sem `batch-id`, um UUID Ã© gerado; para retry idempotente, o mesmo `batch-id` deve ser reutilizado. Testes focados: `4 passed`; diagnÃ³stico do editor sem erros.

Limpeza antes do empacotamento: removidos `src/ingestion/gcs_uploader.py` e `tests/unit/test_gcs_uploader.py`, pois representavam o fluxo intermediÃ¡rio arquivo local -> GCS e foram substituÃ­dos pelo exportador direto PostgreSQL -> GCS. Mantidos o exportador local como fallback/teste, o validador Parquet e os componentes de validaÃ§Ã£o CDC.

Empacotamento local do Cloud Run Job concluÃ­do em 2026-11-07. Foram criados `infra/cloud_run/full_extract/Dockerfile`, `.dockerignore` e `infra/cloud_run/full_extract/README.md`. A imagem `ecommerce-full-extract:dev` foi construÃ­da com sucesso e `docker run --rm ecommerce-full-extract:dev --help` iniciou o mÃ³dulo esperado. O build nÃ£o fez push nem deploy. Testes unitÃ¡rios do exportador: `5 passed`.

ConfiguraÃ§Ã£o Terraform de Secret Manager criada em `infra/terraform/cloud_run_full_extract/`. Ela declara somente containers de secrets e IAM especÃ­fico para a service account `de-ingestion-writer`; nÃ£o declara versÃµes nem valores de secrets. `terraform init` e `terraform validate` executados com sucesso em 2026-11-07 usando `hashicorp/google v7.46.2`. Nenhum secret foi criado ou alterado.

O modulo foi ajustado para incluir tambem `ecommerce-postgres-host`, junto com usuario e senha. O host sera tratado como configuracao protegida para evitar expor o endpoint externo no repositorio. `terraform fmt` e `terraform validate` executados novamente com sucesso; nenhum valor de secret foi inserido.

Teste real do caminho automÃ¡tico executado em 2026-11-07. O job local conectou ao PostgreSQL remoto e gravou diretamente no GCS, sem usar `data/local`. Foi gerado o batch_id `a5764fa4-fb2c-4ec3-88ec-4818cf81f8f5`, com 100 linhas, 1 lote, Parquet e manifesto. A listagem posterior confirmou os dois objetos e o manifesto retornou `status=succeeded`. Este teste validou o caminho de dados direto; a execuÃ§Ã£o ainda ocorreu localmente, nÃ£o em Cloud Run.

`terraform init` e `terraform validate` foram executados com sucesso em 2026-11-07. Provider instalado: `hashicorp/google v7.46.2`. O arquivo `.terraform.lock.hcl` foi gerado e deve ser versionado; `.terraform/` e `terraform.tfvars` permanecem ignorados. Nenhum `plan` ou `apply` foi executado.

Foi criado o mÃ³dulo declarativo em `infra/terraform/gcs/`, sem `init`, `plan` ou `apply`. O mÃ³dulo declara bucket regional Standard, acesso uniforme, prevenÃ§Ã£o de acesso pÃºblico, `force_destroy=false`, lifecycle opcional, service account dedicada e `roles/storage.objectCreator` limitado ao bucket. `terraform fmt -check -diff` foi executado com sucesso usando Terraform `1.16.5`. Nenhum recurso GCP foi criado ou alterado.

ExecuÃ§Ã£o real concluÃ­da para `ecommerce.categorias` e `ecommerce.pedidos`. Ambas as validaÃ§Ãµes retornaram `succeeded`. Para `pedidos`: 1000000 linhas, 20 arquivos, 0 chaves primÃ¡rias duplicadas, 0 nulos nas colunas obrigatÃ³rias e schema compatÃ­vel. Para `categorias`: 100 linhas, 1 arquivo, 0 chaves duplicadas, 0 nulos obrigatÃ³rios e schema compatÃ­vel. RelatÃ³rios foram gravados nas respectivas pastas `data/local/full_extract/`.

Foi criado `src/ingestion/parquet_validator.py`, com testes em `tests/unit/test_parquet_validator.py`. O validador verifica manifesto, arquivos declarados, schema, contagem de linhas, nulos em colunas obrigatÃ³rias e duplicidade de chave primÃ¡ria. ValidaÃ§Ã£o executada em 2026-11-07: `21 passed in 4.20s`; o diagnÃ³stico do editor nÃ£o reportou erros nos arquivos.

Foi criada a primeira etapa do extrator batch em `src/ingestion/postgres_parquet_exporter.py`. Ele foi desenhado para a tabela pequena `ecommerce.categorias` antes de qualquer envio ao GCP e possui:

- conexÃ£o configurada por variÃ¡veis do `.env`, sem credenciais no cÃ³digo;
- transaÃ§Ã£o `REPEATABLE READ READ ONLY`;
- cursor server-side e `fetchmany`, evitando carregar a tabela inteira na memÃ³ria;
- arquivos Parquet Snappy por lote;
- manifesto JSON com tabela, quantidade de linhas, lotes e arquivos gerados;
- validaÃ§Ã£o de identificadores de schema/tabela antes da composiÃ§Ã£o do SQL.

DependÃªncias adicionadas: `psycopg[binary]`, `pyarrow` e `python-dotenv`. Os testes unitÃ¡rios usam dados sintÃ©ticos e nÃ£o acessam o PostgreSQL.

ValidaÃ§Ã£o executada em 2026-11-07: `19 passed in 6.20s`.

ExportaÃ§Ã£o real executada em 2026-11-07 contra `ecommerce.categorias`, com `batch_size=1000`, sem erros. Resultado: 100 linhas, 1 lote, arquivo `part-00000.parquet`, manifesto gerado e status `succeeded`. A execuÃ§Ã£o confirmou conectividade, leitura somente leitura, conversÃ£o PostgreSQL -> Arrow/Parquet e gravaÃ§Ã£o local.

PrÃ³xima atividade: validar o Parquet e o manifesto; depois decidir a primeira tabela de volume maior para teste controlado.

Teste intermediÃ¡rio executado em 2026-11-07 contra `ecommerce.clientes`, com `batch_size=50000`. Resultado: 200000 linhas, 4 lotes, 4 arquivos Parquet Snappy e manifesto `succeeded`. O tempo observado foi de aproximadamente 6,75 segundos e o volume gerado foi de aproximadamente 7,96 MB. Nenhum recurso GCP foi criado ou alterado.

Teste de maior volume executado em 2026-11-07 contra `ecommerce.pedidos`, com `batch_size=50000`. Resultado: 1000000 linhas, 20 lotes, 20 arquivos Parquet Snappy e manifesto `succeeded`. O tempo observado foi de aproximadamente 94 segundos e o volume gerado foi de aproximadamente 54 MB. A consulta anterior de tamanho havia indicado 999559 linhas; a divergÃªncia reforÃ§a que a origem Ã© mutÃ¡vel e que a plataforma deverÃ¡ registrar contagens de origem/destino e executar reconciliaÃ§Ã£o.

- Fase: 0 — descoberta e planejamento.
- Situação: descoberta inicial da origem concluída; validação de CDC pendente.
- Última atualização: 2026-11-07.

## Decisões confirmadas

- Origem: PostgreSQL 16.15, banco `appdb`.
- Schema de negócio: `ecommerce`.
- Schema `audit`: excluído do escopo deste projeto.
- Schema `public`: sem tabelas de negócio identificadas.
- Região GCP planejada: `us-central1`.
- Projeto GCP informado: `botbrewpub-ghsurp`.
- Ambiente local: Windows, Docker e Python 3.12 com `venv`.
- Runtime CDC do laboratório: Debezium Server neste computador de desenvolvimento, acessando o PostgreSQL Dockerizado remoto pela rede.
- Runtime CDC de produção: opção futura de mover o Debezium para o host da origem ou para um runtime dedicado.
- Primeira validação: começar por uma tabela pequena antes das tabelas de milhões de registros.
- CDC aprovado: Debezium Server enviando eventos diretamente para Google Cloud Pub/Sub.
- Kafka: alternativa documentada, não componente principal neste momento.
- CDC do projeto atual: configuração isolada da anterior, sem reutilizar o slot ou a publicação existentes.
- Nome planejado do slot atual: `ecommerce_gcp_debezium_slot`.
- Nome planejado da publicação atual: `ecommerce_gcp_publication`.
- O projeto não deve armazenar credenciais, tokens ou segredos no repositório.

## Origem descoberta

### Contagem exata de registros

| Tabela | Registros |
|---|---:|
| `ecommerce.armazens` | 5 |
| `ecommerce.categorias` | 100 |
| `ecommerce.clientes` | 200.000 |
| `ecommerce.enderecos_clientes` | 200.000 |
| `ecommerce.envios` | 1.000.000 |
| `ecommerce.estoque` | 500.000 |
| `ecommerce.eventos_clientes` | 10.000.003 |
| `ecommerce.itens_pedido` | 3.000.000 |
| `ecommerce.marcas` | 500 |
| `ecommerce.pagamentos` | 1.000.000 |
| `ecommerce.pedidos` | 1.000.000 |
| `ecommerce.produtos` | 100.000 |
| `ecommerce.variantes_produtos` | 100.000 |

### Tabelas candidatas

- Fatos: `pedidos`, `itens_pedido`, `pagamentos`, `envios`, `eventos_clientes`.
- Dimensões: `clientes`, `produtos`, `variantes_produtos`, `categorias`, `marcas`, `armazens`, `enderecos_clientes`.
- Tabela de estoque: possível fato de snapshot ou entidade operacional, decisão pendente.

### Chaves de atualização identificadas

Colunas de criação:

- `criado_em` em armazéns, categorias, clientes, endereços, envios, marcas, pagamentos, produtos e variantes.

Colunas de atualização:

- `atualizado_em` em clientes, pedidos, produtos e variantes.
- `atualizado_em` em estoque.

Eventos de negócio:

- `eventos_clientes.ocorrido_em`.
- `pedidos.realizado_em`.
- `envios.enviado_em` e `envios.entregue_em`.
- `pagamentos.pago_em`.

Não foi identificado `deleted_at`; deletes físicos devem ser tratados pelo CDC para que eventos `DELETE` sejam preservados na camada Bronze.

## Observações técnicas

- As estatísticas estimadas do PostgreSQL não foram consideradas confiáveis para dimensionamento; as contagens exatas serão utilizadas.
- `eventos_clientes` possui 10.000.003 registros e será a principal tabela para teste de volume.
- `dados_evento` é `jsonb` e exigirá decisão de representação no Parquet e no BigQuery.
- Campos como nome, e-mail, telefone, endereço e CEP exigem tratamento adequado caso dados sejam publicados ou compartilhados.
- A modelagem dimensional só será fechada após validar regras de negócio e granularidade das tabelas.

## Pendências

1. Confirmar a estrutura completa dos índices relevantes.
2. Validar tipos, cardinalidade e valores de negócio das colunas de status.
3. Definir a primeira tabela da carga full.
4. Confirmar configuração de logical replication para o PostgreSQL.
5. Definir retenção e armazenamento dos offsets do Debezium Server.
6. Definir o consumidor Pub/Sub e a estratégia de persistência da Bronze.
7. Definir política de publicação para campos sensíveis.
8. Definir ambientes e estratégia de implantação via Console e Terraform.
9. Criar publicação isolada e configurar o Debezium para criar o novo slot durante a inicialização.
10. Preparar a execução local do Debezium neste computador, usando o PostgreSQL remoto como origem.

## Próxima atividade

Validar o PostgreSQL para CDC somente leitura, verificando configuração de logical replication, publicações existentes, replication slots e permissões disponíveis. Depois será definida a primeira tabela para carga full e o contrato do evento Bronze.

## Registro de validações

- [x] Versão e banco PostgreSQL identificados.
- [x] Schemas e tabelas de negócio identificados.
- [x] Contagens exatas obtidas.
- [x] Chaves primárias identificadas.
- [x] Foreign keys identificadas.
- [x] Colunas de criação, atualização e eventos identificadas.
- [x] Logical replication validada.
- [x] Estratégia de isolamento do CDC anterior definida.
- [x] Publicação CDC isolada criada e validada.
- [x] Template inicial do Debezium Server criado sem credenciais.
- [x] Docker Compose local organizado em `infra/local/` para executar somente o Debezium Server.
- [x] Rotação de logs Docker configurada para limitar o crescimento local.
- [ ] Primeira carga full executada.
- [ ] Primeiro evento CDC recebido no Pub/Sub.
- [ ] Dados Bronze persistidos.

## Primeira execução do Debezium

Em 2026-11-07, após a correção local da senha, o container `ecommerce-gcp-debezium` conectou ao PostgreSQL remoto e iniciou o snapshot. Foram exportados 5 registros de `ecommerce.armazens`; o snapshot de `ecommerce.categorias` também foi iniciado.

A execução falhou no sink Pub/Sub porque os tópicos `ecommerce_gcp.ecommerce.armazens` e `ecommerce_gcp.ecommerce.categorias` ainda não existem no projeto GCP. O container entrou em reinício automático. A criação dos tópicos e assinaturas requer autorização explícita antes de alterar recursos cloud.

### Fluxo observado

1. O Debezium carregou a configuração do PostgreSQL, incluindo `plugin.name=pgoutput`, `publication.name` e `slot.name`.
2. Conectou ao banco `appdb` e leu o catálogo para identificar schemas, tabelas e estruturas.
3. Iniciou o snapshot inicial usando `table.include.list`, que selecionou `ecommerce.armazens` e `ecommerce.categorias` para leitura de dados.
4. Registrou o LSN inicial no slot lógico e exportou eventos `READ` para os registros existentes.
5. Tentou publicar os eventos nos destinos Pub/Sub derivados de `topic.prefix + schema + table`.
6. Falhou porque os tópicos Pub/Sub ainda não existiam; o serviço entrou em reinício automático.

## Validação de logical replication

Resultado obtido em 2026-11-07:

- `wal_level`: `logical`.
- `max_replication_slots`: `10`.
- `max_wal_senders`: `10`.
- Slot existente: `ecommerce_debezium_slot`.
- Tipo do slot: `logical`.
- Plugin: `pgoutput`.
- Banco do slot: `appdb`.
- Estado do slot: `active`.
- Publicação existente: `ecommerce_publication`.
- A publicação possui `publish`: `insert`, `update`, `delete`, `truncate`.
- A publicação não é `FOR ALL TABLES`; as tabelas publicadas ainda precisam ser inventariadas.

Conclusão: o PostgreSQL já possui os parâmetros principais para logical replication e uma configuração de CDC existente. Como o slot está ativo, não criar, reutilizar ou remover recursos até identificar o consumidor atual e confirmar o escopo da publicação.

## Validação do snapshot e streaming do Debezium

Em 2026-11-07, após a criação manual dos tópicos e assinaturas Pub/Sub pelo usuário, o container `ecommerce-gcp-debezium` foi recriado e validado.

- Container: `Up`.
- Snapshot inicial: `COMPLETED`.
- Slot utilizado: `ecommerce_gcp_debezium_slot`.
- LSN armazenado e retomado: `1/71AC0D50`.
- Sink Pub/Sub: inicializado sem o erro anterior de tópico inexistente.
- Streaming: iniciado e processando mensagens a partir do LSN armazenado.
- Escopo atual: `ecommerce.armazens` e `ecommerce.categorias`.

Pendência imediata: consumir uma amostra pelas assinaturas Pub/Sub e validar o envelope JSON dos eventos `READ`. Ainda não foi executado teste de `INSERT`, `UPDATE` ou `DELETE` no PostgreSQL.

## Incidente identificado durante a validação do Pub/Sub

Durante a inspeção das assinaturas, algumas mensagens apareceram repetidas e com `Deadline exceeded`. Há dois comportamentos distintos:

1. Os comandos de pull foram executados sem `--auto-ack`, portanto as mensagens não foram confirmadas e podem ser entregues novamente após o vencimento do ack deadline.
2. O container do Debezium apresentou reinícios consecutivos. A causa-raiz registrada no log foi `INVALID_ARGUMENT` ao tentar publicar o heartbeat no tópico `__debezium-heartbeat.ecommerce_gcp`. Esse nome é inválido para um tópico Pub/Sub porque começa com sublinhado.

Enquanto o heartbeat permanecer configurado dessa forma, o Debezium pode reiniciar e repetir o snapshot, publicando novos eventos para as mesmas chaves. A correção do heartbeat é pré-requisito para validar a unicidade esperada do snapshot.

## Correção do heartbeat

Em 2026-11-07, o heartbeat foi temporariamente desabilitado no laboratório com `debezium.source.heartbeat.interval.ms=0`. O container foi reiniciado explicitamente para recarregar o arquivo montado e validado com:

- `RestartCount=0` após a correção;
- estado `running`;
- streaming iniciado;
- ausência do erro de recurso Pub/Sub inválido na execução validada.

Solução definitiva para reativação: configurar `debezium.source.topic.heartbeat.name=debezium-heartbeat-ecommerce-gcp`, criar esse tópico no Pub/Sub e só então definir um intervalo positivo. O nome explícito evita o nome padrão iniciado por sublinhado (`__debezium-heartbeat.ecommerce_gcp`), incompatível com o Pub/Sub neste cenário. A criação do tópico ainda está pendente de autorização.

Após a criação manual do tópico pelo usuário, o heartbeat foi reativado com intervalo de 10 segundos e validado:

- configuração carregada: `topic.heartbeat.name=debezium-heartbeat-ecommerce-gcp`;
- configuração carregada: `heartbeat.interval.ms=10000`;
- container `running`;
- `RestartCount=0` após a inicialização;
- streaming iniciado sem o erro de recurso inválido.

A futura migração dessa criação manual para Terraform permanece planejada para a fase de infraestrutura como código.

## Estratégia para mensagens duplicadas do Pub/Sub

Em 2026-11-07, foi escolhida a opção de manter o backlog existente e seguir com um consumidor Bronze idempotente. A decisão representa o comportamento de produção de entrega pelo menos uma vez: mensagens podem ser reentregues, e o consumidor deverá confirmar (`ack`) somente após persistência bem-sucedida e deduplicar eventos repetidos.

Não será executado `purge` nas assinaturas atuais. Purge permanece apenas como alternativa de laboratório para remover mensagens pendentes e repetir uma validação limpa.

## Primeiro componente Python do consumidor Bronze

Foi criado um parser inicial e isolado do contrato CDC em `src/ingestion/cdc_contract.py`. Ele valida e normaliza `source.schema`, `source.table`, `op`, `before`, `after`, `source.lsn` e `source.txId`, preservando o envelope original em `raw`.

Testes criados em `tests/unit/test_cdc_contract.py` cobrem:

- evento `READ` de snapshot;
- operações `c`, `u`, `d` e `t`;
- campos obrigatórios ausentes;
- operação inválida.

Validação executada em 2026-11-07: `7 passed in 0.06s`. Nenhum erro foi reportado pelo diagnóstico do editor nos arquivos Python.

Próxima atividade: adicionar o adaptador de leitura Pull do Pub/Sub, inicialmente sem persistência externa, com opção explícita de não confirmar mensagens durante a validação do contrato.

## Adaptador Pull do Pub/Sub

Foram criados:

- `src/ingestion/pubsub_probe.py`: leitor Pull limitado, decodificação Base64/JSON, validação pelo contrato CDC e saída apenas de metadados;
- `tests/unit/test_pubsub_probe.py`: testes do decodificador e da saída sem payload de negócio;
- `requirements.txt`: dependência `google-cloud-pubsub`;
- `requirements-dev.txt`: dependências de desenvolvimento com `pytest`.

O adaptador não confirma mensagens por padrão. A opção `--ack` existe apenas para testes controlados e não deve ser usada como mecanismo de ingestão antes da persistência durável.

Validação executada em 2026-11-07: `10 passed in 2.42s`. Nenhum erro foi reportado pelo diagnóstico do editor nos arquivos Python.

Próxima validação pendente: executar o probe contra uma assinatura Pub/Sub com limite pequeno, sem `--ack`, e confirmar que os metadados dos eventos correspondem ao contrato observado.

### Resultado do probe real

## Writer local da Bronze

Foi criado `src/ingestion/bronze_writer.py` para validacao local. O componente:

- gera `event_id` SHA-256 deterministico do envelope CDC canonizado;
- grava registros append-only em JSONL por tabela;
- mantem um ledger SQLite local de eventos processados;
- ignora reprocessamentos identicos.

Testes criados em `tests/unit/test_bronze_writer.py`. Validacao executada em 2026-11-07: `12 passed in 1.67s`. Nenhum erro foi reportado pelo diagnostico do editor.

Limitacao conhecida: o writer local ainda nao oferece atomicidade transacional entre o ledger SQLite e o arquivo JSONL. Ele e um componente de aprendizado e teste; a versao GCP devera usar uma estrategia duravel e recuperavel antes do `ack` do Pub/Sub.

Proxima atividade: conectar o probe ao writer local em um modo controlado, sem `ack` automatico, e depois desenhar a persistencia equivalente no Cloud Storage.

## Integracao Pub/Sub com Bronze local

O probe foi integrado ao `LocalBronzeWriter` e executado contra a assinatura `ecommerce-gcp-armazens-sub` com limite de 3 mensagens, sem `--ack`.

Resultado observado:

- 3 eventos Debezium decodificados;
- 3 eventos persistidos em `data/local/bronze-armazens/raw/table=armazens/events.jsonl`;
- ledger criado em `data/local/bronze-armazens/state/bronze_ledger.sqlite`;
- diretório `data/local/` ignorado pelo Git;
- nenhuma mensagem confirmada no Pub/Sub.

Validação executada em 2026-11-07. O fluxo local validado foi: Pub/Sub Pull -> decode JSON -> contrato CDC -> event_id -> JSONL Bronze/ledger SQLite.

Proxima etapa: avaliar a persistencia equivalente no Cloud Storage, incluindo bucket, IAM, particionamento de objetos, formato Parquet e estrategia de confirmacao antes de criar recursos cloud.

## Desenho preliminar da Bronze no Cloud Storage

Nenhum recurso GCP foi criado nesta etapa. A proposta em avaliacao e:

- bucket regional em `us-central1`, alinhado ao BigQuery planejado;
- camada raw imutavel preservando o envelope CDC original;
- arquivos Parquet para consumo analitico, mantendo `raw_payload` ou equivalente para auditoria;
- caminho particionado por origem, tabela e data de ingestao;
- nomes de objetos unicos por lote, evitando sobrescrita;
- service account dedicada com menor privilegio, preferencialmente apenas criacao de objetos para o writer;
- lifecycle configuravel para reduzir custo, sem Bucket Lock nesta fase de laboratorio;
- provisionamento manual somente para validacao inicial e migracao posterior para Terraform.

Pendencia: medir o tamanho fisico das tabelas PostgreSQL antes de estimar volume Parquet e custo de armazenamento. Nao criar bucket ate concluir essa medicao e aprovar o desenho.

### Resultado da medicao fisica

Consulta executada pelo usuario em 2026-11-07:

- tamanho das tabelas, sem indices: aproximadamente 2,56 GB decimais / 2,38 GiB;
- tamanho total de tabelas mais indices: aproximadamente 3,83 GB decimais / 3,56 GiB;
- indices representam aproximadamente 1,27 GB adicionais;
- maior tabela: `eventos_clientes`, com aproximadamente 1,63 GB de tabela e 2,36 GB incluindo indices;
- maiores tabelas seguintes: `itens_pedido`, `pedidos`, `pagamentos` e `envios`.

As contagens atuais tambem diferem da descoberta inicial em algumas tabelas, por exemplo `eventos_clientes`, `itens_pedido` e `pedidos`. Isso reforca que o PostgreSQL e mutavel e que a carga full precisa ser coordenada com CDC e reconciliao.

Decisao tecnica proposta: usar Python batch para as tabelas de fatos e para `eventos_clientes`, gravando Parquet no Cloud Storage; manter snapshot Debezium somente para tabelas pequenas usadas na validacao inicial. O volume de 10 milhoes de eventos nao sera enviado como snapshot Debezium para o Pub/Sub.

O probe foi executado sem `--ack` na assinatura `ecommerce-gcp-armazens-sub` e retornou três eventos válidos com operação `r` e `snapshot=true`. Os eventos possuíam `message_id`, `source_lsn` e `transaction_id` diferentes.

Essa diferença confirma que não eram apenas reentregas da mesma mensagem. A verificação posterior mostrou o container com `RestartCount=0`, estado `running`, arquivo `offsets.dat` presente e nenhum novo snapshot/erro recente. Conclusão: os eventos distintos pertencem ao backlog produzido durante os reinícios anteriores do Debezium; não há evidência de novo reinício no momento.

O probe não confirmou (`ack`) nenhuma mensagem. A próxima etapa será implementar persistência durável antes de habilitar confirmação.
## Secret Manager para o job de carga full

O mÃ³dulo Terraform em `infra/terraform/cloud_run_full_extract/` foi validado em 2026-11-07. O plano resultou em `6 to add, 0 to change, 0 to destroy`; nenhum `apply` foi executado.

Recursos planejados:

- trÃªs contÃªineres de segredos: host, usuÃ¡rio e senha do PostgreSQL;
- trÃªs bindings `roles/secretmanager.secretAccessor` para `de-ingestion-writer@botbrewpub-ghsurp.iam.gserviceaccount.com`.

Valores e versÃµes dos segredos nÃ£o serÃ£o criados pelo Terraform, evitando credenciais no estado. PrÃ³xima pendÃªncia: aprovaÃ§Ã£o explÃ­cita para executar o `terraform apply` desses seis recursos.
## Aplicação dos contêineres do Secret Manager

Em 2026-11-07, o módulo `infra/terraform/cloud_run_full_extract/` foi aplicado com autorização explícita.

Resultado: `6 added, 0 changed, 0 destroyed`.

Validação realizada sem leitura de valores sensíveis:

- os três segredos esperados existem: host, usuário e senha do PostgreSQL;
- o segredo `ecommerce-postgres-host` possui `roles/secretmanager.secretAccessor` para `de-ingestion-writer@botbrewpub-ghsurp.iam.gserviceaccount.com`;
- nenhuma versão/valor foi criado pelo Terraform.

Também foi identificado um segredo preexistente chamado `postgres-source-database-url`, que não foi alterado por este módulo. Ele deverá ser avaliado posteriormente quanto a origem, uso e necessidade de migração; não será removido sem autorização.

Próxima etapa: inserir os três valores no Secret Manager por procedimento seguro e depois preparar a configuração do Cloud Run Job para referenciá-los, sem colocar credenciais no repositório ou no estado Terraform.
## Versões dos segredos do PostgreSQL

Em 2026-11-07, foram verificadas versões ativas nos três segredos sem leitura dos valores:

- `ecommerce-postgres-host`: versão `1` habilitada;
- `ecommerce-postgres-user`: versão `1` habilitada;
- `ecommerce-postgres-password`: versão `1` habilitada.

Os valores permanecem fora do repositório, desta conversa e do estado Terraform.

Próxima atividade: configurar o Cloud Run Job para injetar esses segredos como variáveis de ambiente e validar a execução com uma tabela pequena.
## Imagem do Cloud Run Job no Artifact Registry

Em 2026-11-07, a imagem local `ecommerce-full-extract:dev` foi publicada manualmente no Artifact Registry:

`us-central1-docker.pkg.dev/botbrewpub-ghsurp/data-engineering/ecommerce-full-extract:dev`

Digest retornado pela publicação:

`sha256:6cfd8bf7ecac8c4c38130ef8263e1736cb619c5fda484de1b685728efa857c8d`

A mensagem `Mounted from botbrewpub-ghsurp/data-platform/ingestion` indica que uma camada idêntica já existia no registro e foi reutilizada. A publicação terminou com sucesso.

Decisão registrada: a publicação manual será usada para compreender e validar o primeiro job. Posteriormente, GitHub Actions deverá construir, testar e publicar imagens versionadas por SHA do commit; produção deverá referenciar imagem imutável por digest ou tag de release.

Próxima atividade: criar e executar o Cloud Run Job pelo Console usando o digest acima.
## Primeira execução do Cloud Run Job

Em 2026-11-07, o job `ecommerce-full-extract-categorias` foi executado pelo Console com a imagem versionada por digest.

Resultado observado nos logs:

- status: `succeeded`;
- origem: `ecommerce.categorias`;
- registros extraídos: `100`;
- lotes: `1`;
- formato: Parquet;
- compressão: Snappy;
- encerramento do container: `exit(0)`.

Objetos gerados no Cloud Storage:

`bronze/parquet/source=postgresql/schema=ecommerce/table=categorias/ingestion_date=2026-11-07/batch_id=ab9d25c9-e7a4-44e1-a3ab-8661df7f9017/`

O resultado comprova o fluxo PostgreSQL -> Cloud Run Job -> Cloud Storage, sem persistência intermediária local.

Próxima atividade: validar a presença do Parquet e do `manifest.json` no bucket e executar uma segunda carga controlada para observar comportamento de reexecução e geração de novo `batch_id`.
## Segunda execução e validação de lotes

Em 2026-11-07, o job `ecommerce-full-extract-categorias` foi executado novamente com sucesso.

Resultado observado:

- status: `succeeded`;
- registros: `100`;
- lotes: `1`;
- novo `batch_id`: `faa6e658-0c12-4daf-b960-49e186348e99`;
- container: `exit(0)`.

O segundo lote foi gravado em um prefixo diferente do primeiro, confirmando que a geração automática de `batch_id` evita sobrescrita entre execuções. Esta validação cobre isolamento físico e rastreabilidade dos lotes; deduplicação lógica e reconciliação serão tratadas nas camadas analíticas.

Critério de aceite do Cloud Run Job para a tabela pequena: aprovado.

Próxima atividade: definir e criar o dataset Bronze no BigQuery e carregar os Parquets gerados, preservando metadados de origem, lote e ingestão.
## Avaliação de falha e reexecução do full extract

Avaliação do exporter atual:

- cada execução recebe um `batch_id` UUID diferente;
- o Parquet é gravado antes do `manifest.json`;
- o manifesto só é publicado depois do fechamento bem-sucedido do Parquet;
- `if_generation_match=0` impede sobrescrever um objeto já existente;
- portanto, um lote concluído não é sobrescrito por uma nova execução.

Limitação importante: o exporter atual não retoma um Parquet interrompido no meio. Em uma falha, pode existir um objeto Parquet parcial sem manifesto, e uma nova execução extrai a tabela novamente em um novo lote. O downstream ainda não possui um catálogo/ledger que impeça carregar simultaneamente dois lotes completos no BigQuery.

Decisão de evolução antes de cargas grandes:

1. o carregador do BigQuery deverá aceitar somente lotes com manifesto `status=succeeded`;
2. deverá existir um controle de lotes com estado `started`, `succeeded` ou `failed`;
3. a publicação deverá usar prefixo temporário e promoção lógica do lote concluído;
4. para retomada real, o full extract deverá ser dividido em partes determinísticas, com checkpoints por chave/faixa, em vez de depender de um único Parquet;
5. o BigQuery deverá carregar um lote aprovado uma única vez, com reconciliação de linhas e bytes.

O job pequeno de `categorias` validou isolamento de objetos, mas não valida ainda retomada, deduplicação downstream ou exatamente uma carga analítica. Essas capacidades permanecem pendentes antes de executar tabelas com milhões de registros.
## Decisão sobre qualidade na Bronze e Silver

Decisão confirmada em 2026-11-07: a camada Bronze representa uma cópia técnica da origem e não deve corrigir, descartar ou reinterpretar dados do PostgreSQL.

Na Bronze serão priorizadas validações técnicas de ingestão, como:

- arquivo e manifesto presentes;
- status do lote concluído;
- contagem de registros compatível com a extração;
- schema legível;
- rastreabilidade de origem, tabela e lote.

Regras de qualidade analítica, incluindo nulos obrigatórios, duplicidades, chaves, integridade referencial, padronização e regras de negócio, serão implementadas na Silver com Dataform assertions e modelos SQLX.

A validação realizada até aqui para `ecommerce_bronze.categorias_raw` foi a contagem de 100 registros. Não será criada uma etapa adicional de validação de nulos na Bronze neste momento.
## Mudança de prioridade: automatização ponta a ponta

Decisão confirmada em 2026-11-07: antes de avançar para Silver/Dataform, o projeto deverá automatizar o fluxo completo para todas as tabelas selecionadas:

`PostgreSQL -> Cloud Run Jobs -> Cloud Storage Bronze -> BigQuery Bronze`

A tabela `categorias` continuará sendo o teste técnico já concluído, mas não haverá expansão manual tabela a tabela pelo Console.

Próxima linha de implementação:

1. definir catálogo de tabelas e estratégia de carga;
2. tornar o `batch_id` determinístico por execução e tabela;
3. publicar metadados de lote e controlar estados;
4. adaptar o Cloud Run Job para execução parametrizada por tabela;
5. criar carga idempotente do GCS para BigQuery;
6. orquestrar todas as tabelas com Composer/Airflow;
7. validar contagens, falhas, retries e reexecuções antes de escalar para os maiores volumes.

O avanço para Silver/Dataform fica dependente do aceite do pipeline automatizado Bronze ponta a ponta.
## Fase 1: descoberta do contrato de ingestao

Foi criado `docs/sql/discover_ingestion_metadata.sql` com consultas somente leitura para confirmar:

- chaves primarias;
- foreign keys;
- colunas candidatas a watermark;
- chaves e indices unicos.

Nenhum recurso cloud foi criado ou alterado nesta etapa e nenhuma alteracao foi feita no PostgreSQL. O catalogo de ingestao permanecera pendente ate a execucao dessas consultas e a confirmacao da semantica dos campos de data.

Proxima atividade: executar as consultas no banco `appdb`, compartilhar somente os resultados estruturais e montar o catalogo das tabelas sem incluir dados pessoais ou credenciais.
## Catalogo de ingestao concluido

Em 2026-11-07, foram recebidos os resultados das consultas de metadados do PostgreSQL e confirmado o catalogo das 13 tabelas. O detalhe esta em `docs/INGESTION_CATALOG.md`.

Confirmacoes principais:

- todas as tabelas possuem PK declarada;
- `estoque` possui PK composta por `armazem_id` e `variante_id`;
- foram confirmadas 18 foreign keys;
- nao foi identificado `deleted_at`; deletes fisicos dependem do Debezium CDC;
- candidatos a watermark foram separados de timestamps de negocio;
- indices unicos relevantes foram registrados.

Decisao: executar full batch inicial para todas as tabelas e manter CDC como mecanismo de mudancas posteriores. Watermarks serao usados de forma complementar, somente onde a semantica de atualizacao for adequada.

Proxima atividade: transformar o catalogo em configuracao de execucao do pipeline, sem ainda criar recursos cloud adicionais.
## Configuracao inicial das tabelas

Foi criado `config/ingestion_tables.json` com o contrato executavel inicial das 13 tabelas.

O arquivo registra:

- schema e banco de origem;
- estrategia full inicial;
- exigencia de CDC para mudancas posteriores;
- PK de cada tabela;
- contagem observada;
- candidato a watermark ou coluna de tempo de evento;
- tamanho de lote inicial para benchmark;
- ordem logica de carga.

Validacao local executada em 2026-11-07: JSON valido, 13 tabelas, nomes sem duplicidade, estrategia `full` e CDC requerido.

Os tamanhos de lote sao parametros iniciais e ainda precisam ser medidos em execucao real. No exporter atual, `batch_size` controla grupos de leitura/row groups dentro do Parquet; ainda nao representa checkpoint ou varios objetos independentes.

Proxima atividade: alterar o exporter para receber e persistir um `batch_id` deterministico, metadados de lote e estados de controle antes de orquestrar a carga completa.
## Identidade deterministica de lotes

O exporter foi ajustado para aceitar `--run-id` e derivar um identificador estavel no formato `run_id__schema__table`. O `--batch-id` explicito continua suportado para controle direto; execucoes manuais sem ambos continuam usando UUID.

O `manifest.json` agora registra:

- `batch_id`;
- `run_id`;
- `ingestion_mode=full`;
- metadados de origem e contagem ja existentes.

Testes adicionados cobrem determinismo, rejeicao de `run_id` inseguro e parsing da nova opcao. Validacao executada em 2026-11-07: `29 passed in 1.44s`; diagnostico do editor sem erros nos arquivos alterados.

Esta etapa ainda nao implementa retomada parcial nem ledger externo de estados. O proximo desenho deve decidir onde persistir `started`, `failed` e `succeeded` antes de adicionar checkpoints ou a carga automatizada para o BigQuery.
## Validação real do full extract retomável

Em 2026-11-07, a imagem atualizada foi construída, publicada e aplicada ao job existente `ecommerce-full-extract`.

Imagem publicada:

`us-central1-docker.pkg.dev/botbrewpub-ghsurp/data-engineering/ecommerce-full-extract@sha256:92893a169ab045b46d9d4d8b22d3922341c2841222e16da4111646eb40b6e3cc`

A execução controlada de `ecommerce.categorias` foi concluída com sucesso e produziu:

- `checkpoint.json`;
- `part-00000.parquet`;
- `manifest.json` com `status=succeeded`;
- `100` registros;
- `batch_id` determinístico derivado do `run_id`.

O mesmo `run_id` foi executado novamente. A segunda execução também terminou com sucesso e manteve exatamente os mesmos três objetos, comprovando a idempotência do lote concluído.

Durante a validação foram encontrados e corrigidos dois problemas reais:

1. o override de argumentos do Cloud Run podia chegar como uma string única; o runner agora normaliza esse formato;
2. checkpoints exigem leitura, atualização e exclusão de objetos; a service account passou a usar `roles/storage.objectUser`, aplicado pelo Terraform, em vez da combinação insuficiente de `objectCreator` e `objectViewer`.

Os testes locais finais totalizaram `34 passed`. O diagnóstico do editor não apontou erros nos arquivos Python alterados.

Ficam no bucket alguns prefixos de testes anteriores e um prefixo de execução que falhou antes de publicar manifesto. Esses objetos não são considerados lotes válidos pelo pipeline, pois somente manifestos com `status=succeeded` devem ser consumidos. A limpeza desses objetos será tratada por lifecycle ou rotina explícita, sem exclusão manual nesta etapa.

Critério de aceite desta frente: extração PostgreSQL -> Cloud Run Job -> GCS com catálogo, partes Parquet, checkpoint, manifesto, retry idempotente e IAM mínimo operacional: aprovado para a tabela de validação. A execução das 13 tabelas em volume completo ainda deve ser feita como carga operacional controlada, preferencialmente uma tabela por task/orquestração.
## Recuperacao de lote interrompido validada

O lote de teste `full_20261107T211025Z_581c0e0a__ecommerce__categorias` havia criado uma parte antes da falha de permissao IAM. Depois da troca para `roles/storage.objectUser`, o mesmo `run_id` foi executado novamente.

Resultado: execucao concluida com sucesso e o prefixo ficou com exatamente um `part-00000.parquet`, um `checkpoint.json` e um `manifest.json`. Nao foi criado um segundo Parquet para os mesmos registros.

Essa validacao comprova a recuperacao de uma parte ja enviada, alem da idempotencia de um lote que ja possuia manifesto de sucesso.

## Carga full das 13 tabelas concluida

Em 2026-11-07, o job `ecommerce-full-extract` foi atualizado para a imagem corrigida:

`us-central1-docker.pkg.dev/botbrewpub-ghsurp/data-engineering/ecommerce-full-extract@sha256:e942146a72185848fa98f822c77e49f83881d40ea740f1fe6492784598063a10`

A execucao `ecommerce-full-extract-w22pp` foi retomada com o mesmo `run_id` `full_20261107T213000Z_all`. O mecanismo reutilizou manifests ja concluidos e continuou a partir do checkpoint da tabela `eventos_clientes`.

Resultado operacional:

- execucao Cloud Run concluida com sucesso;
- 13 manifests finais com `status=succeeded` no GCS;
- todas as 13 tabelas do catalogo foram processadas;
- `eventos_clientes` foi concluida com `10000003` registros em `401` partes Parquet;
- o ultimo lote de eventos contem apenas `3` registros, preservando a contagem real da origem;
- o checkpoint final e o manifest foram publicados somente apos a conclusao da tabela.

Durante a primeira tentativa da carga completa, a tabela `eventos_clientes` revelou incompatibilidade entre `uuid`/`jsonb` do PostgreSQL e a inferencia do PyArrow. O runner foi ajustado para normalizar UUID para texto e JSONB para JSON estavel antes da escrita Parquet. A nova imagem foi publicada e a mesma carga foi retomada sem duplicar o prefixo logico.

Validacoes realizadas:

- suite local: `35 passed`;
- execucao Cloud Run full: sucesso;
- manifests das tabelas: `armazens`, `categorias`, `clientes`, `enderecos_clientes`, `envios`, `estoque`, `eventos_clientes`, `itens_pedido`, `marcas`, `pagamentos`, `pedidos`, `produtos` e `variantes_produtos`;
- recuperacao de falha e retry idempotente: aprovados;
- Terraform do bucket e IAM: sem alteracoes pendentes no ultimo plan.

Conclusao da frente na validacao original: a extracao full PostgreSQL -> Cloud Run Jobs -> GCS Bronze foi validada para o volume observado, com carga em lotes, Parquet, manifest, checkpoint e retry idempotente de lotes ja concluidos. A retomada parcial foi desabilitada posteriormente por seguranca de consistencia; ver a secao de revisao abaixo. A camada de leitura no BigQuery, o CDC para Bronze e a orquestracao com Composer permanecem como proximas frentes.

## Revisao de producao e correcoes de seguranca da extracao

Revisao posterior identificou que a retomada de partes de uma tabela em uma nova execucao nao preserva o snapshot PostgreSQL da execucao anterior. Para evitar misturar estados da origem, o comportamento foi alterado: lotes com checkpoint mas sem manifest de sucesso falham de forma fechada; deve-se iniciar um novo `run_id`, que cria um prefixo isolado. Os objetos do prefixo interrompido nao sao elegiveis para consumo por downstream e ficam sujeitos a retencao/lifecycle. Portanto, a validacao historica de retomada parcial continua sendo evidência do comportamento anterior, mas nao e mais o criterio de retomada da implementacao atual.

Outras correcoes:

- `ingestion_date` e inferida de um `run_id` com data; se o `run_id` manual nao contiver data, `--ingestion-date` passa a ser obrigatoria para garantir que repeticoes apontem ao mesmo prefixo;
- criado `execution.lock` com precondicao de geracao do GCS, impedindo duas execucoes simultaneas do mesmo lote;
- checkpoint passa a guardar apenas contagem de partes, linhas e ultima chave, em vez de regravar a lista crescente de metadados de todas as partes em cada lote;
- falhas de lock cleanup sao emitidas como log de warning; um lock abandonado exige verificar primeiro se a execucao anterior terminou.

Limite arquitetural ainda aberto: a consistencia entre a fotografia full feita pelo Python e o fluxo CDC do Debezium nao esta coordenada por LSN nem reconciliada em um destino. Antes de declarar o pipeline full+CDC consistente, definir fronteira de captura, ordenacao/deduplicacao por chave e LSN, e reconciliacao de deletes. O BigQuery e Composer ainda nao foram integrados.

### Correcao implantada no Cloud Run Job

Em 2026-11-07, a revisao de consistencia foi validada e implantada no job `ecommerce-full-extract` sem disparar uma nova carga full.

Validacoes executadas:

- suite local completa: `39 passed`;
- diagnostico do editor: nenhum erro nos arquivos Python alterados;
- `git diff --check`: aprovado, somente avisos de conversao de fim de linha LF/CRLF;
- build da imagem: aprovado;
- smoke test do container com `--help`: aprovado;
- Cloud Run Job: condicao `Ready=True`, geracao `9`.

Imagem implantada por digest imutavel:

`us-central1-docker.pkg.dev/botbrewpub-ghsurp/data-engineering/ecommerce-full-extract@sha256:adc3bd26983961a6410baaf3079df1f7965bffb1dd4e0e5a8d75c3cc0d39bd9c`

A versao implantada inclui validacao estrita de `ingestion_date` no formato `YYYY-MM-DD`, bloqueio atomico por prefixo, checkpoints compactos e falha fechada para lotes interrompidos. Manifests de lotes concluidos continuam idempotentes. Nenhuma extracao PostgreSQL nem escrita adicional de dados Bronze foi executada durante esta implantacao.

Proxima decisao arquitetural obrigatoria: definir a fronteira entre full e CDC por LSN e a estrategia de deduplicacao/reconciliacao no destino antes de automatizar a carga Bronze no BigQuery e antes de introduzir o Composer.

## Contrato CDC-first aprovado e implementado localmente

Em 2026-11-09 foi aprovada a estrategia `cdc_first_replay`: iniciar um ciclo CDC isolado antes de uma nova fotografia full e reaplicar no destino todos os eventos desde um limite inferior seguro do slot.

Fundacao implementada:

- contrato `CdcEpoch` com identificador, LSN PostgreSQL e representacao inteira comparavel ao `source.lsn` do Debezium;
- argumentos `--cdc-epoch-id` e `--cdc-start-lsn` no full extract, obrigatorios em conjunto;
- manifesto full classificado como `coordinated` ou `uncoordinated`;
- template Debezium v2 com novo slot, offsets isolados, `snapshot.mode=no_data`, prefixo de topicos v2 e as 13 tabelas;
- documento de coordenacao com regras de deduplicacao, ordenacao por chave, replay e deletes;
- validacao automatica confirmou 13 tabelas no catalogo e 13 tabelas no template Debezium;
- suite local: `48 passed`; diagnostico do editor sem erros.

Nenhum slot, topico, assinatura ou outro recurso externo foi criado ou alterado. O Debezium nao foi reiniciado e nenhuma nova carga full foi executada.

Proxima atividade controlada: definir no console os 13 topicos e assinaturas v2, revisar custo/retencao, iniciar o novo slot com uma unica instancia do Debezium, registrar `restart_lsn` como limite inferior e validar insert/update/delete antes de executar uma nova carga full coordenada.

## Terraform Pub/Sub CDC v2 preparado

Foi criado o modulo `infra/terraform/pubsub_cdc` como fonte declarativa dos recursos de transporte do ciclo CDC v2.

O modulo declara:

- 13 topicos com nomes compativeis com o `topic.prefix` do Debezium;
- 13 assinaturas Pull com ordering, retry com backoff e expiracao desabilitada;
- retencao de sete dias nos topicos para replay parametrizado;
- um topico e uma assinatura de Dead Letter;
- IAM do service agent do Pub/Sub para publicar na DLQ e reconhecer mensagens das assinaturas.

Validacoes realizadas em 2026-11-09:

- Terraform `v1.16.5`;
- provider Google `v7.46.2`;
- `terraform fmt -check`: aprovado;
- `terraform validate`: aprovado;
- `terraform plan`: `42 to add, 0 to change, 0 to destroy`.

Nenhum recurso foi criado. O `apply` permanece pendente de revisao e autorizacao explicita. O plano foi executado contra `botbrewpub-ghsurp` apenas para leitura.

Observacao de producao: o template Debezium ainda usa offsets em arquivo local para o laboratorio. Antes de declarar o runtime CDC pronto para producao, deve ser escolhido e implementado um armazenamento duravel de offsets/schema history e um runtime continuamente disponivel.

Antes do apply, o modulo foi endurecido para o padrao profissional:

- criada service account `de-cdc-publisher`;
- publisher restrito por IAM aos 13 topicos CDC;
- politica padrao de destruicao `ABANDON` para topicos e assinaturas;
- output da identidade que devera ser associada ao runtime Debezium;
- documentado que ADC local nao usa automaticamente essa service account;
- mantida a necessidade de backend remoto Terraform em bucket dedicado antes de producao.

Novo plano somente leitura: `56 to add, 0 to change, 0 to destroy`. Nenhum recurso foi criado. O apply continua pendente de autorizacao explicita e revisao do state/backend.

## Pub/Sub CDC v2 aplicado e verificado

Em 2026-11-09, com autorizacao explicita, o modulo Terraform corrigido foi aplicado no projeto `botbrewpub-ghsurp`.

Resultado:

- `56 added, 0 changed, 0 destroyed`;
- 13 topicos CDC v2 criados;
- 13 assinaturas Pull criadas;
- topico e assinatura de Dead Letter criados;
- service account `de-cdc-publisher@botbrewpub-ghsurp.iam.gserviceaccount.com` criada;
- publisher da service account restrito aos 13 topicos;
- IAM do service agent Pub/Sub aplicado para DLQ e reconhecimento das assinaturas;
- Terraform plan posterior: `No changes`;
- verificacao GCP: 14 topicos e 14 assinaturas encontrados, incluindo DLQ.

O Debezium ainda nao foi iniciado e nenhum slot PostgreSQL foi criado ou alterado. O state permanece local para o laboratorio; backend remoto GCS e persistencia duravel de offsets continuam pendentes antes de uma classificacao de producao.

## Preparacao do heartbeat CDC v2

Em 2026-11-09, o modulo Pub/Sub foi ajustado localmente para declarar tambem o
topico `ecommerce_gcp_v2.heartbeat`, sua assinatura Pull e a permissao de
publisher da service account dedicada do Debezium. O heartbeat foi habilitado
no template ativo e no exemplo com intervalo de 10 segundos.

Tambem foi atualizado localmente o arquivo ativo do Debezium para o ciclo v2:
slot `ecommerce_gcp_v2_debezium_slot`, offsets/schema history em
`/debezium/data/v2`, `snapshot.mode=no_data` e as 13 tabelas da publication.

Estado desta atividade:

- alteracoes locais aplicadas nos arquivos de Terraform e propriedades;
- `terraform fmt` aprovado;
- `terraform validate` aprovado;
- `terraform plan` somente leitura aprovado: `3 to add, 0 to change, 0 to destroy`;
- apply autorizado e concluido: `3 added, 0 changed, 0 destroyed`;
- topico `ecommerce_gcp_v2.heartbeat` criado com retencao de sete dias;
- assinatura `ecommerce-gcp-v2-heartbeat-sub` criada e ativa;
- permissao `roles/pubsub.publisher` aplicada a `de-cdc-publisher` no topico de heartbeat;
- verificacao via gcloud confirmou o topico, a assinatura e o estado `ACTIVE`;
- novo `terraform plan` confirmou `No changes`;
- o Debezium nao foi iniciado nem reiniciado;
- proxima acao condicionada: iniciar o Debezium v2 em uma unica instancia e observar os eventos;
- a existencia do topico/assinatura foi validada; o Debezium v2 ainda deve ser
  iniciado somente na proxima etapa controlada.

## Debezium v2 iniciado e corrigido

Em 2026-11-09 o container local foi recriado com a configuracao v2. A primeira
tentativa revelou uma falha real de persistencia: os caminhos apontavam para
`/debezium/data/v2/`, mas o diretorio nao existia no volume montado. O processo
chegou a conectar no PostgreSQL, porem falhou ao salvar offsets com
`NoSuchFileException`.

Tratamento aplicado:

- container parado para interromper novas tentativas;
- offsets v2 alterados para `/debezium/data/offsets-v2.dat`;
- schema history v2 alterado para `/debezium/data/schema-history-v2.dat`;
- arquivo legado `offsets.dat` preservado;
- container recriado e validado como `running`;
- arquivo `offsets-v2.dat` criado no volume;
- logs confirmaram `snapshot.mode=no_data`, slot
  `ecommerce_gcp_v2_debezium_slot`, inicio do streaming e processamento de mensagens;
- assinatura de heartbeat recebeu mensagens do Debezium.

Observacao operacional: o log registra um aviso recomendando avaliar
`heartbeat.action.query` para reduzir risco de crescimento de WAL em periodos de
baixa atividade. O heartbeat Pub/Sub esta funcionando, mas essa recomendacao
deve ser avaliada antes de classificar o runtime como pronto para producao.

## Teste controlado de INSERT, UPDATE e DELETE

Em 2026-11-09 foi executado um teste controlado em `ecommerce.armazens` com a
chave temporaria `armazem_id=1000005`. Cada operacao foi confirmada em uma
transacao separada:

- `INSERT`: capturado com `op=c`, `snapshot=false`, LSN `6202073400`;
- `UPDATE`: capturado com `op=u`, `snapshot=false`, LSN `6202079472`;
- `DELETE`: capturado com `op=d`, `snapshot=false`, LSN `6202080568`.

As tres mensagens chegaram na assinatura
`ecommerce-gcp-v2-armazens-sub` com a ordering key correspondente. A validacao
foi feita via gcloud Pull, sem ack, porque ainda nao existe um consumidor
duravel Bronze que possa confirmar a mensagem somente depois da persistencia.

Observacao de contrato: as tabelas estao com `REPLICA IDENTITY DEFAULT`. Para
DELETE, o destino deve usar a chave primaria (`before`/ordering key) para
remover a linha; os demais campos anteriores nao devem ser tratados como
before-image completo. Alterar para `REPLICA IDENTITY FULL` e uma alternativa
que aumenta o volume de WAL e sera avaliada somente se o caso de uso exigir
before-images completos.

## Fronteira full GCS para BigQuery

Os arquivos Parquet full existentes no GCS continuam sendo a landing Bronze de
arquivos. A carga deles no dataset BigQuery sera feita na etapa de
materializacao Bronze, depois da implementacao do consumidor CDC persistente e
de uma nova fotografia full coordenada pelo `epoch_id` e `start_lsn`.

Os arquivos produzidos em 2026-11-07 foram gerados antes da fronteira CDC e
permanecem classificados como `uncoordinated`. Eles podem ser usados para
validacao de laboratorio ou backfill, mas nao devem ser apresentados como a
carga full+CDC definitiva.

Fluxo aprovado para a proxima etapa de BigQuery:

1. receber CDC em um consumidor duravel e persistir o envelope Bronze;
2. executar full coordenado PostgreSQL -> Parquet -> GCS;
3. carregar Parquet em tabelas staging/bronze do BigQuery com manifest e
   `WRITE_TRUNCATE` restrito ao lote;
4. validar contagem e manifest;
5. reaplicar CDC desde `start_lsn` com deduplicacao por `event_id`;
6. publicar o estado Silver somente depois da reconciliacao.

Assim, o BigQuery sera introduzido na fase de materializacao Bronze, nao na
fase de transporte inicial PostgreSQL -> GCS.

## Decisao sobre Parquets antigos e nova imagem do full

Os Parquets antigos nao serao removidos antes da nova carga coordenada ser
concluida e reconciliada. Para o laboratorio, eles poderao ser removidos
depois dessa validacao ou submetidos a uma politica de lifecycle direcionada
ao prefixo `uncoordinated`; nenhuma limpeza destrutiva foi executada.

Foi verificado que o Cloud Run Job `ecommerce-full-extract` ainda usa a imagem
digest `adc3bd26983961a6410baaf3079df1f7965bffb1dd4e0e5a8d75c3cc0d39bd9c`,
atualizada em 2026-11-07, e esta configurado apenas com
`--table=categorias`. A implementacao de coordenacao por
`--cdc-epoch-id`/`--cdc-start-lsn` foi adicionada ao codigo em 2026-11-09.

Decisao: gerar uma nova imagem imutavel do full extract, publicar no Artifact
Registry e atualizar o Cloud Run Job para usar o novo digest e os argumentos
da carga coordenada.

Execucao controlada em 2026-11-09:

- testes focados: `17 passed`;
- imagem construida e publicada com a tag
  `full-coordinated-20261109-a44bec4`;
- digest publicado:
  `sha256:1c1e20a0626f58a4d4469c2efc8758279d8994eee19d9c574023b402e18d43c2`;
- `restart_lsn` consultado no slot v2: `1/71AC40C0`;
- `epoch_id`: `epoch_20261109_001`;
- Cloud Run Job atualizado para a imagem por digest e para executar o catalogo
  completo sem `--table` especifica;
- argumentos configurados: `--run-id=full_20261109_001`,
  `--cdc-epoch-id=epoch_20261109_001`, `--cdc-start-lsn=1/71AC40C0`;
- Job na geracao `10`, condicao `Ready=True`;
- os Parquets antigos continuam preservados.

## Full coordenado concluido no GCS

Em 2026-11-09 foi executada a carga full coordenada pelo Cloud Run Job. A
execucao `ecommerce-full-extract-z76tp` iniciou em `2026-11-09T11:23:10Z` e
terminou em `2026-11-09T12:10:38Z`, com duracao de `47m27.59s`,
`succeededCount=1` e condicao `Completed=True`.

Validacao dos manifests no novo lote:

- 13 de 13 tabelas com `status=succeeded`;
- 17.100.608 linhas extraidas;
- 546 arquivos Parquet/batches;
- todas as tabelas registraram `cdc_coordination.status=coordinated`;
- todas registraram `epoch_id=epoch_20261109_001` e `start_lsn=1/71AC40C0`;
- `eventos_clientes` registrou 10.000.003 linhas e `itens_pedido` registrou
  3.000.000 linhas, valores efetivos do snapshot que devem prevalecer sobre
  estimativas/estatisticas anteriores do catalogo.

A imagem configurada no Job permanece referenciada pelo digest imutavel
`sha256:1c1e20a0626f58a4d4469c2efc8758279d8994eee19d9c574023b402e18d43c2`;
na execucao, o Cloud Run registrou o digest de plataforma
`sha256:b8eca6a09b0287f67dab8923b9f3a1121cfc92a091f09a71949d86fc7080742f`.
Essa diferenca deve ser mantida documentada e revisada no pipeline de
build/deploy, sem alterar a carga ja concluida.

Uma carga full coordenada ainda nao foi materializada no BigQuery pelo novo
materializer. A proxima etapa autorizada deve ser a materializacao Bronze no BigQuery,
precedida pela definicao/validacao do consumidor CDC duravel e pela
reconciliacao do full com os eventos desde o LSN inicial.

## Limpeza dos ingests antigos e desenho da materializacao Bronze

Em 2026-11-09, depois da validacao dos 13 manifests coordenados de
`full_20261109_001`, foram removidos do GCS somente os objetos sob:

`bronze/parquet/source=postgresql/schema=ecommerce/table=*/ingestion_date=2026-11-07/`

Resultado da pre-validacao: 588 objetos, aproximadamente 873,42 MiB. A
remocao nao incluiu o prefixo de `2026-11-09`; um manifesto coordenado de
`categorias` foi lido novamente apos a limpeza com `status=succeeded`, 100
linhas e `epoch_20261109_001`. O bucket possui soft delete, permitindo
recuperacao operacional durante a janela configurada.

Foi criado o materializer
`src/materialization/bigquery_full_materializer.py`. Ele trabalha uma tabela
por tarefa, monta o manifesto a partir dos parametros, rejeita cargas
`uncoordinated`, carrega explicitamente as partes Parquet em staging, compara
as contagens e publica a particao logica do mesmo `run_id` em uma transacao
BigQuery. A tabela Bronze recebe metadados de linhagem e e particionada por
`_ingestion_date`, com clustering pela chave primaria.

O nome da tabela destino agora e configuravel por `--target-table`; quando
omitido, o contrato usa `bronze_<tabela_origem>`. Essa convencao cria um
destino novo, como `ecommerce_bronze.bronze_categorias`, e nao sobrescreve a
tabela manual legada `ecommerce_bronze.categorias_raw`.

O materializer foi empacotado separadamente em
`infra/cloud_run/materializer/`. Foi criado
`requirements-materializer.txt` com somente as dependencias de BigQuery e
Cloud Storage. O catalogo deixou de importar o exportador PostgreSQL apenas
para validar identificadores; o helper compartilhado esta em
`src/ingestion/identifiers.py`. Isso evita instalar Pub/Sub, psycopg e pyarrow
na imagem do materializer.

Tambem foi criado o modulo `infra/terraform/cloud_run_materializer/`, que
declara a service account dedicada e as permissoes minimas de leitura no GCS,
execucao de jobs BigQuery e escrita no dataset Bronze. `terraform fmt`,
`terraform init -backend=false` e `terraform validate` foram aprovados. Nao
foi executado `apply`, e nenhum recurso GCP foi alterado durante a validacao
inicial. Com autorizacao explicita, o `apply` foi executado em 2026-11-09 e
criou 4 recursos: a service account
`de-bronze-materializer@botbrewpub-ghsurp.iam.gserviceaccount.com`, o leitor
do bucket, `BigQuery Job User` no projeto e `BigQuery Data Editor` no dataset
Bronze. O plan posterior confirmou `No changes`.

Decisao arquitetural: a copia fisica GCS -> BigQuery fica no materializer
Python, que sera chamado futuramente pelo Composer/Cloud Run Job. O Dataform
sera acionado depois da Bronze materializada para Silver/Gold, assertions,
deduplicacao e regras de negocio. Dataform nao sera usado como controlador
principal do transporte de arquivos e manifests.

Validacao local desta etapa: `55 passed` na suite unitária. O build local da
imagem otimizada e o smoke test `--help` tambem foram aprovados. O dataset BigQuery
ja existia antes desta etapa. A imagem foi publicada no Artifact Registry com
a tag `materializer-20261109-01` e o digest
`sha256:f518e6f2ed52764a3fa3ba83ca52a8c0f061ccd956d5e06720b73f8c525cc610`.
O Job Cloud Run `ecommerce-bronze-materializer` foi criado pelo Terraform em
`us-central1`, esta `Ready=True` na geracao 1 e usa a service account dedicada,
2 vCPU, 4 GiB, timeout de 3600 segundos e um retry. O plan posterior confirmou
`No changes`. O Job ainda nao foi executado; portanto nenhuma tabela nova foi
materializada no BigQuery. O DAG do Composer ainda nao foi criado.

## Materializacao Bronze full concluida

Em 2026-11-09, apos a remocao autorizada da tabela manual legada
`ecommerce_bronze.categorias_raw`, o Job foi executado uma vez para cada uma
das 13 tabelas do catalogo, com overrides de `table`, `target-table`, `run-id`
e `ingestion-date`. Todas as execucoes terminaram com sucesso.

Validacao somente leitura no BigQuery:

- 13 tabelas `bronze_<tabela>` criadas no dataset `ecommerce_bronze`;
- 17.100.608 linhas publicadas, correspondentes aos manifests full;
- todas as linhas possuem `run_id=full_20261109_001`;
- todas as linhas possuem `epoch_id=epoch_20261109_001`;
- todas as tabelas estao particionadas por `_ingestion_date`;
- todas estao clusterizadas pela chave primaria definida no catalogo;
- datas de ingestao confirmadas como `2026-11-09`.

Essa execucao conclui o transporte PostgreSQL -> GCS -> BigQuery Bronze para
o ciclo full coordenado. Ainda nao representa a reconciliacao final full+CDC,
porque o consumidor CDC duravel e a reaplicacao dos eventos desde o LSN
inicial ainda precisam ser implementados.
## Reconciliação do estado BigQuery existente

Em 2026-11-09 foi feita uma consulta somente leitura no projeto
`botbrewpub-ghsurp`. Foi confirmado que o dataset `ecommerce_bronze` ja existe
em `us-central1` e possui a tabela `categorias_raw` com 100 registros. O
schema atual contem `categoria_id`, `categoria_pai_id`, `nome_categoria` e
`criado_em`, sem os metadados de linhagem previstos no novo materializer.

Conclusao: `ecommerce_bronze.categorias_raw` e uma evidencia de uma etapa
anterior/manual e nao deve ser sobrescrita automaticamente. O novo
materializer ainda nao foi executado. A convencao de destino aprovada para a
primeira carga e manter essa tabela como legado de laboratorio e publicar uma
tabela Bronze nova com o contrato de metadados, usando o nome padrao ou um
nome explicito via `--target-table`.

Essa verificacao corrige a informacao historica de secoes anteriores deste
arquivo que afirmavam que nenhum dataset BigQuery existia. O estado real do
GCP passa a ser a referencia operacional; os registros anteriores permanecem
como historico das etapas em que foram escritos.

## Automatizacao futura do full e da materializacao

O Cloud Run Job `ecommerce-full-extract` ainda esta configurado com os
argumentos fixos da primeira carga coordenada:
`--run-id=full_20261109_001`, `--cdc-epoch-id=epoch_20261109_001` e
`--cdc-start-lsn=1/71AC40C0`. Isso foi intencional para tornar o primeiro ciclo
reprodutivel e auditavel; nao e o desenho final de operacao.

Na versao orquestrada, o Composer devera disparar um componente coordenador
que gera o `run_id`, consulta/valida o LSN inicial do slot CDC, cria o registro
imutavel do `epoch_id` e passa somente uma referencia de controle ao full
extract. Os valores continuarao existindo tecnicamente para linhagem e
reprocessamento, mas nao serao digitados manualmente pelo operador.

O Composer devera controlar a sequencia:

1. criar o ciclo CDC e registrar o LSN inicial;
2. executar o Cloud Run Job de extração PostgreSQL -> GCS;
3. validar os manifests coordenados;
4. executar o materializer GCS -> BigQuery Bronze por tabela;
5. reconciliar o full com o CDC persistido;
6. disparar o workflow Dataform para Silver e Gold.

O Composer sera o orquestrador e o Cloud Run executara as cargas pesadas. O
Dataform nao sera usado como controlador principal da copia fisica GCS ->
BigQuery.

## DAG local do Composer para a materializacao Bronze

Em 2026-11-09 foi criada a primeira DAG local de orquestracao em
`orchestration/composer/dags/ecommerce_bronze_materialization.py`. Ela nao
cria recursos GCP nem foi enviada a um ambiente Composer. O desenho usa um
unico Cloud Run Job reutilizavel e mapeia uma tarefa por tabela, com limite de
quatro tarefas simultaneas. A lista de tabelas fica em
`materialization_plan.py` e possui teste de sincronizacao com
`config/ingestion_tables.json`.

A DAG recebe `run_id` e `ingestion_date` do ciclo full coordenado, monta os
overrides do materializer e permite reprocessamento seletivo por tabela. O
default reproduz o ciclo `full_20261109_001`, mas o uso operacional devera
passar os valores pelo `dag_run.conf` gerado pelo coordenador do pipeline.

Foi escolhida inicialmente a execucao nao-deferrable para nao assumir que o
futuro ambiente Composer tera triggerer habilitado. Depois da criacao e
validacao do Composer, a operacao podera habilitar o modo deferrable para
reduzir o consumo de slots do worker durante o polling do Cloud Run.

Validacao local desta etapa: `60 passed` na suite completa, incluindo cinco
testes do plano; sintaxe dos dois arquivos Python validada; diagnostico do
editor sem erros; `git diff --check` sem problemas. Nenhum deploy Composer foi
realizado.

## Preparacao do ambiente Composer

Em 2026-11-09 foi preparado o modulo
`infra/terraform/composer/`, ainda sem `apply`. O modulo declara uma service
account dedicada, `roles/composer.worker`, `roles/run.jobsExecutorWithOverrides`
e `roles/run.viewer` no Cloud Run Job materializer, alem do ambiente Composer
3 com a versao de imagem informada em `terraform.tfvars`.

O equivalente manual esta documentado no README do modulo. A escolha
operacional desta etapa e Composer 3 pequeno, resiliÃªncia padrao e sem
triggerer enquanto a DAG permanecer `deferrable=False`. O modo de
desenvolvimento hibernÃ¡vel continua como alternativa de laboratorio pelo
Console, mas nao e representado pelo modulo Terraform atual.

Nenhum ambiente Composer foi criado, nenhuma permissao IAM foi aplicada e
nenhuma DAG foi enviada ao bucket do ambiente. O proximo passo exige escolha
do caminho de provisionamento: Console ou `terraform apply` revisado.

Validacao local do modulo: `terraform fmt -check`, `terraform init
-backend=false` e `terraform validate` aprovados com
`hashicorp/google v7.46.2` e `hashicorp/google-beta v7.46.2`. O arquivo
`.terraform.lock.hcl` do modulo foi gerado para versionamento; nenhum recurso
cloud foi aplicado.

Tentativa inicial de criacao do Composer pelo Console em 2026-11-09 falhou
com a mensagem `The zone or region does not have sufficient resources to
handle the request at the moment`. O erro indicou indisponibilidade
temporaria de capacidade na infraestrutura da regiao, e nao falha de IAM ou
da DAG.

## Ambiente Composer criado

Em 2026-11-09 o ambiente foi criado com sucesso pelo Console:

- nome: `ecommerce-composer-lab`;
- regiao: `us-central1`;
- versao informada: `2.11.1-build.23`;
- Airflow: acessivel pelo link gerado pelo ambiente;
- bucket de DAGs: `us-central1-ecommerce-compo-9b6b94ee-bucket`.

As DAGs deste repositorio foram publicadas no bucket `dags/` e a DAG
`ecommerce_bronze_materialization` apareceu no Airflow sem erro de importacao.

## Primeira execucao Composer: falha de template corrigida

Em 2026-11-09 foi disparada uma execucao manual da DAG pelo Console. O
Console nao exibiu formulario de `dag_run.conf` e criou a execucao com
`dag_run.conf = None`. A tarefa `build_materialization_plan` foi concluida,
mas as 13 tarefas mapeadas falharam durante a renderizacao Jinja antes de
chamar o Cloud Run, com o erro:

`jinja2.exceptions.UndefinedError: 'None' has no attribute 'get'`

As expressoes de configuracao do operador foram corrigidas para usar
`(dag_run.conf or {}).get(...)`, preservando os overrides via JSON e tratando
o acionamento sem configuracao. A correcao foi validada com 61 testes,
compilacao dos arquivos Composer, `git diff --check` e diagnostico do editor
sem erros. A DAG corrigida ainda precisa ser reenviada ao bucket `dags/` e
validada em uma nova execucao.

## Segunda execucao Composer: override de argumentos corrigido

Na execucao seguinte, a DAG passou pela renderizacao Jinja e chamou o Cloud
Run, confirmando que a primeira correcao foi publicada. O Cloud Run rejeitou a
solicitacao porque o override continha uma lista `args` junto com
`clear_args=true`:

`Args list for override must be empty when clear_args field is set to true`

O plano em `materialization_plan.py` foi corrigido para nao enviar
`clear_args`. A API do Cloud Run substitui os argumentos existentes quando
recebe a lista `args`, e o container do materializer possui um `ENTRYPOINT`
sem argumentos fixos. A correcao foi validada com 61 testes, compilacao dos
arquivos Composer, `git diff --check` e diagnostico do editor sem erros.
A proxima atividade e reenviar `materialization_plan.py`, aguardar a
sincronizacao e executar novamente a DAG.

## Terceira execucao Composer: permissao de polling do Cloud Run pendente

Na execucao seguinte, o Cloud Run aceitou o pedido e criou operacoes de
execucao, mas o worker do Composer falhou ao consultar o estado dessas
operacoes com:

`Permission 'run.operations.get' denied`

O problema esta na identidade usada pelo worker do Composer ou no escopo do
binding IAM. `roles/run.jobsExecutorWithOverrides` permite iniciar o Job com
overrides, enquanto `roles/run.viewer` inclui a leitura de operacoes. A
proxima atividade e confirmar a service account real do ambiente Composer e
garantir `roles/run.viewer` no escopo do projeto para essa identidade,
mantendo `roles/run.jobsExecutorWithOverrides` no Job materializer. Nenhuma
nova execucao deve ser disparada antes dessa verificacao. Tambem e necessario
verificar no Cloud Run se as execucoes criadas antes da falha de polling
terminaram.

## Execucao Composer validada

Em 2026-11-09, apos corrigir o binding IAM da service account usada pelo
ambiente Composer, a DAG `ecommerce_bronze_materialization` foi executada
com sucesso. O Composer conseguiu iniciar e acompanhar as execucoes do Cloud
Run materializer para as tabelas Bronze. O upload manual no bucket `dags/`
foi utilizado apenas para esta validacao inicial.

Proxima evolucao operacional: versionar as DAGs e seus modulos auxiliares no
GitHub e substituir o upload manual por CI/CD, com validacao, testes e envio
controlado ao bucket do Composer a partir de um commit revisado.

## CI inicial para DAGs e Python

Foi criado `.github/workflows/ci.yml` para executar, em Pull Requests e
pushes na branch `main`:

- instalacao de `requirements-dev.txt` com Python 3.12;
- suite completa de testes unitarios;
- compilacao/sintaxe de `src`, das DAGs Composer e dos testes.

Esse workflow nao acessa GCP, nao publica DAGs e nao usa credenciais. A
proxima evolucao sera um workflow separado de deploy para o bucket do
Composer, autenticado via Workload Identity Federation e executado somente
apos a aprovacao do Pull Request.
