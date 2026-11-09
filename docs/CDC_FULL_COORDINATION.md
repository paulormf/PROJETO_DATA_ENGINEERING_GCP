# Coordenacao entre full e CDC

## Decisao

O projeto usa a estrategia `cdc_first_replay`:

1. iniciar um ciclo CDC isolado antes da fotografia full;
2. registrar o LSN inicial do ciclo;
3. executar o full Python para Parquet no GCS;
4. carregar o full como estado-base;
5. reaplicar todos os eventos CDC do ciclo em ordem sobre esse estado.

Essa estrategia aceita sobreposicao. Um insert ou update ja visivel na fotografia pode aparecer novamente no CDC; a materializacao deve ser idempotente e convergir pelo ultimo evento da chave. Um delete remove a chave.

## Contrato do ciclo

Cada ciclo possui:

- `epoch_id`: identificador imutavel e versionado;
- `start_lsn`: limite inferior seguro do ciclo, registrado a partir de `restart_lsn` do novo slot no formato hexadecimal `HEX/HEX`;
- `start_lsn_int`: representacao inteira comparavel com `source.lsn` do Debezium;
- slot, offsets e prefixo de topicos exclusivos;
- lista das 13 tabelas esperadas.

Uma carga full coordenada recebe `--cdc-epoch-id` e `--cdc-start-lsn`. Os dois argumentos sao obrigatorios em conjunto. O manifesto registra `cdc_coordination.status=coordinated` e `strategy=cdc_first_replay`. Sem os argumentos, o lote fica `uncoordinated` e nao pode alimentar uma materializacao full+CDC de producao.

Exemplo apenas estrutural:

```text
--cdc-epoch-id epoch_YYYYMMDD_NNN --cdc-start-lsn HEX/HEX
```

## Regras para o BigQuery

Bronze preserva o recebido e nao aplica regras de qualidade de negocio. Para cada tabela, a materializacao Silver deve:

1. aceitar exatamente um lote full bem-sucedido por `epoch_id`;
2. rejeitar manifests `uncoordinated`, incompletos ou de outro ciclo;
3. deduplicar CDC pelo `event_id` deterministico;
4. considerar somente eventos com `source_lsn >= start_lsn_int`;
5. ordenar eventos da mesma chave por LSN e metadados de transacao;
6. usar `after` para create/update e `before` para localizar deletes;
7. excluir a chave quando o ultimo evento for `d`;
8. reconciliar contagens e registrar divergencias sem alterar a Bronze.

Pub/Sub oferece entrega pelo menos uma vez. Ordering key reduz reordenacao por chave, mas nao substitui deduplicacao nem torna toda a transacao atomica no BigQuery.

## Ativacao pendente

Antes de iniciar o Debezium v2:

- criar e validar os 13 topicos com prefixo `ecommerce_gcp_v2` e suas assinaturas;
- confirmar que a publicacao contem exatamente as tabelas do catalogo;
- garantir persistencia e backup operacional dos offsets;
- iniciar uma unica instancia do conector;
- consultar o novo slot e registrar `restart_lsn` como limite inferior antes do full, sem remover ou reutilizar o slot anterior;
- produzir uma alteracao controlada e confirmar o evento no novo topico;
- somente entao executar uma nova carga full coordenada.

O slot antigo nao deve ser removido nesta etapa. A carga full de 2026-11-07 permanece evidencia de desempenho e funcionamento, mas e classificada como `uncoordinated` para consistencia full+CDC.
