# Project Status

## Objetivo

Construir uma plataforma de Engenharia de Dados na GCP para o domínio de e-commerce, usando PostgreSQL como origem, arquitetura Medallion, BigQuery, Dataform, Cloud Composer, Debezium, Pub/Sub, observabilidade, qualidade de dados e CI/CD.

## Status atual

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

O probe foi executado sem `--ack` na assinatura `ecommerce-gcp-armazens-sub` e retornou três eventos válidos com operação `r` e `snapshot=true`. Os eventos possuíam `message_id`, `source_lsn` e `transaction_id` diferentes.

Essa diferença confirma que não eram apenas reentregas da mesma mensagem. A verificação posterior mostrou o container com `RestartCount=0`, estado `running`, arquivo `offsets.dat` presente e nenhum novo snapshot/erro recente. Conclusão: os eventos distintos pertencem ao backlog produzido durante os reinícios anteriores do Debezium; não há evidência de novo reinício no momento.

O probe não confirmou (`ack`) nenhuma mensagem. A próxima etapa será implementar persistência durável antes de habilitar confirmação.
