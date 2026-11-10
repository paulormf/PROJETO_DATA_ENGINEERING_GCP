const dimTempo = publish("dim_tempo", {
  type: "table",
  schema: "ecommerce_gold",
  tags: ["gold", "dimension"],
  description: "Calendario analitico derivado do intervalo de datas dos pedidos.",
});

dimTempo.query((ctx) => `
WITH raw_bounds AS (
  SELECT
    COALESCE(MIN(DATE(realizado_em)), CURRENT_DATE()) AS min_data,
    COALESCE(MAX(DATE(realizado_em)), CURRENT_DATE()) AS max_data
  FROM ${ctx.ref("silver_pedidos")}
  WHERE _ingested_at >= TIMESTAMP('1970-01-01')
), bounds AS (
  SELECT
    min_data,
    GREATEST(max_data, min_data, CURRENT_DATE()) AS max_data
  FROM raw_bounds
)
SELECT
  CAST(FORMAT_DATE('%Y%m%d', calendar_date) AS INT64) AS data_key,
  calendar_date AS data,
  EXTRACT(YEAR FROM calendar_date) AS ano,
  EXTRACT(QUARTER FROM calendar_date) AS trimestre,
  EXTRACT(MONTH FROM calendar_date) AS mes,
  EXTRACT(ISOWEEK FROM calendar_date) AS semana_iso,
  EXTRACT(DAYOFWEEK FROM calendar_date) AS dia_semana,
  EXTRACT(DAYOFWEEK FROM calendar_date) IN (1, 7) AS fim_de_semana
FROM bounds
CROSS JOIN UNNEST(GENERATE_DATE_ARRAY(min_data, max_data)) AS calendar_date
`);

const dimCliente = publish("dim_cliente", {
  type: "table",
  schema: "ecommerce_gold",
  tags: ["gold", "dimension", "pii-controlled"],
  description: "Dimensao de clientes sem exposicao de nome, email ou telefone em Gold.",
});

dimCliente.query((ctx) => `
SELECT
  cliente_id,
  status_cliente,
  criado_em,
  atualizado_em,
  _ingested_at AS _silver_ingested_at
FROM ${ctx.ref("silver_clientes")}
WHERE _is_deleted = FALSE
`);

const dimArmazem = publish("dim_armazem", {
  type: "table",
  schema: "ecommerce_gold",
  tags: ["gold", "dimension"],
  description: "Dimensao de armazens para analise operacional e de fulfillment.",
});

dimArmazem.query((ctx) => `
SELECT
  armazem_id,
  nome_armazem,
  cidade,
  estado,
  criado_em,
  _ingested_at AS _silver_ingested_at
FROM ${ctx.ref("silver_armazens")}
WHERE _is_deleted = FALSE
`);

const dimProdutoSku = publish("dim_produto_sku", {
  type: "table",
  schema: "ecommerce_gold",
  tags: ["gold", "dimension"],
  description: "Dimensao de SKU enriquecida com produto, marca e categoria.",
});

dimProdutoSku.query((ctx) => `
SELECT
  v.variante_id,
  v.sku,
  v.nome_variante,
  v.produto_id,
  p.nome_produto,
  p.status_produto,
  v.ativo AS variante_ativa,
  v.preco_custo,
  v.preco_venda,
  v.peso_gramas,
  p.marca_id,
  m.nome_marca,
  p.categoria_id,
  c.nome_categoria,
  v.criado_em,
  v.atualizado_em,
  GREATEST(
    COALESCE(v._ingested_at, TIMESTAMP('1970-01-01')),
    COALESCE(p._ingested_at, TIMESTAMP('1970-01-01')),
    COALESCE(m._ingested_at, TIMESTAMP('1970-01-01')),
    COALESCE(c._ingested_at, TIMESTAMP('1970-01-01'))
  ) AS _silver_ingested_at
FROM ${ctx.ref("silver_variantes_produtos")} AS v
LEFT JOIN ${ctx.ref("silver_produtos")} AS p
  ON p.produto_id = v.produto_id
  AND p._is_deleted = FALSE
LEFT JOIN ${ctx.ref("silver_marcas")} AS m
  ON m.marca_id = p.marca_id
  AND m._is_deleted = FALSE
LEFT JOIN ${ctx.ref("silver_categorias")} AS c
  ON c.categoria_id = p.categoria_id
  AND c._is_deleted = FALSE
WHERE v._is_deleted = FALSE
`);
