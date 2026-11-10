# Dataflow Streaming isolado

Este pipeline e um laboratorio controlado para praticar Apache Beam Streaming.
Ele nao usa os topicos reais do Debezium e nao e iniciado por GitHub Actions.

Fluxo:

```text
Pub/Sub sintetico -> Beam Streaming -> janela event-time -> deduplicacao por event_id -> BigQuery shadow
                                      \-> DLQ Pub/Sub
```

O Dockerfile e o `metadata.json` deixam o Flex Template pronto para uma
publicacao manual futura. A publicacao e a execucao devem ocorrer somente por
`workflow_dispatch` ou por um procedimento operacional aprovado. Nao existe
Terraform aplicando um job Streaming permanente.

Para encerrar um job Streaming, use drain quando a continuidade dos dados for
importante ou cancel quando for somente um laboratorio. Depois da validacao,
o job deve permanecer parado para evitar custo recorrente.
