# Pub/Sub CDC v2

Este modulo declara a camada de transporte do ciclo CDC v2:

- um topico por tabela, com o mesmo nome esperado pelo Debezium Server;
- uma assinatura Pull por tabela, com ordering habilitado;
- retencao no topico para permitir replay durante o bootstrap full;
- retry com backoff;
- uma Dead Letter Topic compartilhada e assinatura de quarentena;
- um topico de heartbeat e uma assinatura Pull para manter o LSN avancando quando houver pouca escrita nas tabelas;
- IAM do service agent do Pub/Sub para publicar na DLQ e reconhecer mensagens das assinaturas.
- service account dedicada do Debezium com permissao de publisher somente nos 13 topicos CDC;
- politica padrao `ABANDON`, evitando apagar topicos acidentalmente durante um destroy.

## Nomes

Com os valores padrao, o Debezium publica em nomes como:

```text
ecommerce_gcp_v2.ecommerce.armazens
ecommerce_gcp_v2.ecommerce.eventos_clientes
```

As assinaturas sao nomeadas como `ecommerce-gcp-v2-<tabela>-sub`.

O heartbeat usa o topico `ecommerce_gcp_v2.heartbeat` e a assinatura
`ecommerce-gcp-v2-heartbeat-sub`. O Debezium deve publicar no topico somente
depois que o topico existir e a service account dedicada tiver o papel de
publisher nesse recurso.

## Validacao

Na raiz do repositorio:

```powershell
terraform -chdir=infra/terraform/pubsub_cdc init
terraform -chdir=infra/terraform/pubsub_cdc fmt -check
terraform -chdir=infra/terraform/pubsub_cdc validate
terraform -chdir=infra/terraform/pubsub_cdc plan -var-file=terraform.tfvars
```

O `plan` e somente leitura. Nao execute `apply` sem revisar o plano e autorizar explicitamente a criacao dos recursos.

O output `debezium_publisher_service_account_email` identifica a identidade que devera ser associada ao runtime do Debezium. A execucao local atual usa ADC e nao passa a usar essa identidade automaticamente.

## Operacao

O Terraform e a fonte de verdade. Criacoes manuais no Console podem ser usadas para aprendizado, mas devem ser importadas ou removidas antes do apply para evitar drift. A retencao de sete dias e um parametro inicial de laboratorio; para producao, deve ser dimensionada pelo RPO, tempo maximo de recuperacao e volume CDC.

O modulo ainda usa state local durante o laboratorio. Antes de producao, configurar backend remoto GCS em bucket dedicado, com IAM minimo, versionamento e procedimento de recuperacao.
