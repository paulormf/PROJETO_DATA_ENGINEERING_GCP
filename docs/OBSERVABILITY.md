# Observabilidade e operacao

Este projeto usa os sinais nativos dos servicos e nao provisiona alertas ou
recursos de monitoramento pagos enquanto o laboratorio estiver desligado.
Quando o ambiente for ativado, os mesmos sinais podem ser ligados a Cloud
Monitoring, notificacoes e SLAs.

## Sinais por etapa

| Etapa | Sinal de sucesso | Sinal de falha ou atraso |
| --- | --- | --- |
| Cloud Run Jobs | execucao `Succeeded` e JSON final com `status=succeeded` | execucao `Failed`, `exit(1)` ou ausencia do objeto esperado no GCS |
| GCS Raw/Bronze | manifesto com `status=succeeded`, contagem e objetos imutaveis | manifesto ausente/incompleto, conflito de precondicao ou contagem divergente |
| Dataflow Batch | estado `JOB_STATE_DONE`, metricas Beam e tabela Bronze atualizada | `JOB_STATE_FAILED`, rejeitos na DLQ ou metricas de registros invalidos |
| Pub/Sub CDC | mensagens entregues e confirmadas pelo consumidor | backlog, redelivery, dead-letter ou erro HTTP 5xx |
| Dataform | compilacao/invocacao verde e assertions aprovadas | assertion falha, compilacao invalida ou tabela sem atualizacao |
| CI/CD | checks do GitHub Actions verdes e imagem por digest | teste, compilacao, push ou deploy falho |

## Consultas e filtros uteis

No Cloud Logging, filtre por `resource.type="cloud_run_job"` e pelo label
`resource.labels.job_name`. Para uma execucao especifica, use tambem
`labels."run.googleapis.com/execution_name"`.

No Dataflow, consulte o estado do job, as metricas `processed_records`,
`valid_records` e `invalid_records`, e o prefixo de dead-letter informado no
parametro da execucao.

No Pub/Sub, acompanhe o backlog da assinatura e a quantidade de mensagens
encaminhadas para a dead-letter topic. A entrega e pelo menos uma vez; por
isso, redelivery nao deve ser tratado como duplicidade definitiva sem conferir
o `event_id` no Bronze/Silver.

No BigQuery, use as assertions do Dataform, contagens por `batch_id`,
`source_lsn` e `_ingested_at`, sempre aplicando filtro de particao em tabelas
particionadas.

## Procedimento de incidente

1. Identificar o `run_id`, `batch_id`, job e objeto de entrada.
2. Confirmar se o artefato de entrada existe e se o manifesto esta completo.
3. Separar erro de transporte, validacao, permissao IAM e regra de modelo.
4. Reexecutar somente com o mesmo identificador quando a etapa for segura para
   retry; objetos Raw sao protegidos por precondicao de nao sobrescrita.
5. Conferir a tabela destino e a DLQ antes de considerar o incidente encerrado.

## Alertas futuros

Nao ha um modulo Terraform de alertas ativo neste momento para evitar custos e
recursos desnecessarios. Em uma ativacao de producao, criar alertas para:

- falha de Cloud Run Job, Dataflow ou Dataform;
- backlog e dead-letter do Pub/Sub;
- ausencia de dados dentro do SLA;
- falha de assertion ou divergencia de contagem;
- crescimento anormal de DLQ e custo.
