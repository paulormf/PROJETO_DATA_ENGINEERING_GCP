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

## Ativacao validada

- os 13 topicos com prefixo `ecommerce_gcp_v2`, heartbeat, dead letter e suas
  assinaturas ja foram criados e verificados na GCP;
- a publicacao contem exatamente as 13 tabelas do catalogo;
- o slot `ecommerce_gcp_v2_debezium_slot` esta ativo;
- o `restart_lsn` registrado para o ciclo foi `1/71AC40C0`;
- uma instancia unica do conector esta em streaming e enviou eventos;
- insert, update e delete controlados foram confirmados no topico da tabela
  `armazens`;
- a carga full coordenada foi executada e os manifests foram validados.

Ainda pendem para a classificacao de producao: consumidor CDC duravel,
persistencia operacional de offsets fora do volume local, materializacao
idempotente no destino e observabilidade do consumidor.

O slot antigo nao deve ser removido nesta etapa. A carga full de 2026-11-07
foi classificada como `uncoordinated` e seus objetos foram removidos do GCS
depois da validacao do full coordenado de 2026-11-09. A evidencia operacional
permanece registrada neste repositorio e no historico de execucao.
