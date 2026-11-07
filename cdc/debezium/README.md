# Debezium Server CDC

Esta pasta contém a primeira configuração do Debezium Server para o projeto de e-commerce.

## Objetivo desta etapa

Capturar inicialmente as tabelas pequenas `ecommerce.armazens` e `ecommerce.categorias`, usando a publicação `ecommerce_gcp_publication` e o slot `ecommerce_gcp_debezium_slot`, enviando os eventos para o Google Cloud Pub/Sub.

## Estado

- A publicação PostgreSQL já foi criada e validada.
- O slot novo ainda não foi criado; o Debezium deverá criá-lo ao iniciar.
- Nenhum recurso GCP foi criado por esta etapa.
- O arquivo `application.properties.example` não contém credenciais.

## Local de execução

Para a validação inicial, o Debezium Server será executado neste computador de desenvolvimento, enquanto acessa o PostgreSQL Dockerizado no outro computador pela rede.

Em uma evolução de produção, poderemos mover o Debezium para o host do PostgreSQL ou para um runtime dedicado, mantendo o CDC próximo da origem.

Neste computador ficarão durante o laboratório:

- Debezium Server em Docker;
- arquivo `.env` com as variáveis de execução;
- diretório persistente para offsets e schema history.

O PostgreSQL continuará no outro computador.

## Preparação no computador de desenvolvimento

1. Copiar `application.properties.example` para `application.properties`.
2. Na raiz do projeto, copiar `.env.example` para `.env` no host que executará o Debezium e preencher as variáveis localmente.
3. Configurar credenciais ADC locais do gcloud para que o container possa publicar no Pub/Sub.
4. Confirmar que o arquivo de credenciais ADC existe em `%APPDATA%\\gcloud\\application_default_credentials.json`.
5. A partir da raiz do projeto, iniciar somente o serviço `debezium-server` com `docker compose -f infra/local/docker-compose.yml up -d debezium-server`.
6. Validar o snapshot inicial e o estado do slot no PostgreSQL.

O arquivo preenchido e o diretório `data/` não devem ser versionados.

## Critérios de aceite

- Debezium inicia sem criar ou alterar a publicação existente.
- O slot `ecommerce_gcp_debezium_slot` é criado pelo Debezium.
- O snapshot gera eventos para `armazens` e `categorias`.
- O consumidor do Pub/Sub recebe eventos JSON.
- Um `INSERT`, `UPDATE` e `DELETE` controlado é refletido nos eventos.
- O offset persiste após reinicialização.
