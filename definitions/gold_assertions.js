assert("gold_dim_tempo_integrity").query((ctx) => `
SELECT data_key
FROM ${ctx.ref("dim_tempo")}
WHERE data_key IS NULL OR data IS NULL

UNION ALL

SELECT data_key
FROM ${ctx.ref("dim_tempo")}
GROUP BY data_key
HAVING COUNT(*) > 1
`);

assert("gold_dim_cliente_integrity").query((ctx) => `
SELECT cliente_id
FROM ${ctx.ref("dim_cliente")}
WHERE cliente_id IS NULL

UNION ALL

SELECT cliente_id
FROM ${ctx.ref("dim_cliente")}
GROUP BY cliente_id
HAVING COUNT(*) > 1
`);

assert("gold_dim_produto_sku_integrity").query((ctx) => `
SELECT variante_id
FROM ${ctx.ref("dim_produto_sku")}
WHERE variante_id IS NULL

UNION ALL

SELECT variante_id
FROM ${ctx.ref("dim_produto_sku")}
GROUP BY variante_id
HAVING COUNT(*) > 1
`);

assert("gold_fct_pedido_item_integrity").query((ctx) => `
SELECT item_pedido_id
FROM ${ctx.ref("fct_pedido_item")}
WHERE item_pedido_id IS NULL

UNION ALL

SELECT item_pedido_id
FROM ${ctx.ref("fct_pedido_item")}
GROUP BY item_pedido_id
HAVING COUNT(*) > 1
`);

assert("gold_fct_pedido_item_dimension_integrity").query((ctx) => `
SELECT CAST(f.item_pedido_id AS STRING) AS item_pedido_id
FROM ${ctx.ref("fct_pedido_item")} AS f
LEFT JOIN ${ctx.ref("dim_produto_sku")} AS d
  ON d.variante_id = f.variante_id
WHERE d.variante_id IS NULL
`);

assert("gold_mart_vendas_diarias_grain").query((ctx) => `
SELECT
  CONCAT(
    CAST(data_pedido AS STRING),
    '|', COALESCE(canal_venda, ''),
    '|', COALESCE(moeda, ''),
    '|', COALESCE(CAST(categoria_id AS STRING), '')
  ) AS grain_key
FROM ${ctx.ref("mart_vendas_diarias")}
GROUP BY grain_key
HAVING COUNT(*) > 1
`);

assert("gold_fct_pedido_item_source_reconciliation").query((ctx) => `
WITH source_metrics AS (
  SELECT
    COUNT(*) AS source_rows,
    COALESCE(SUM(total_item), CAST(0 AS NUMERIC)) AS source_total_item
  FROM ${ctx.ref("silver_itens_pedido")}
  WHERE _is_deleted = FALSE
), fact_metrics AS (
  SELECT
    COUNT(*) AS fact_rows,
    COALESCE(SUM(total_item), CAST(0 AS NUMERIC)) AS fact_total_item
  FROM ${ctx.ref("fct_pedido_item")}
)
SELECT
  'row_count' AS metric,
  CAST(source_rows AS NUMERIC) AS source_value,
  CAST(fact_rows AS NUMERIC) AS gold_value
FROM source_metrics
CROSS JOIN fact_metrics
WHERE source_rows != fact_rows

UNION ALL

SELECT
  'total_item' AS metric,
  source_total_item AS source_value,
  fact_total_item AS gold_value
FROM source_metrics
CROSS JOIN fact_metrics
WHERE source_total_item != fact_total_item
`);

assert("gold_mart_vendas_diarias_reconciliation").query((ctx) => `
WITH fact_metrics AS (
  SELECT
    COUNT(*) AS fact_items,
    COALESCE(SUM(total_item), CAST(0 AS NUMERIC)) AS fact_revenue
  FROM ${ctx.ref("fct_pedido_item")}
), mart_metrics AS (
  SELECT
    COALESCE(SUM(quantidade_itens), 0) AS mart_items,
    COALESCE(SUM(receita_itens), CAST(0 AS NUMERIC)) AS mart_revenue
  FROM ${ctx.ref("mart_vendas_diarias")}
)
SELECT
  'item_count' AS metric,
  CAST(fact_items AS NUMERIC) AS fact_value,
  CAST(mart_items AS NUMERIC) AS mart_value
FROM fact_metrics
CROSS JOIN mart_metrics
WHERE fact_items != mart_items

UNION ALL

SELECT
  'revenue' AS metric,
  fact_revenue AS fact_value,
  mart_revenue AS mart_value
FROM fact_metrics
CROSS JOIN mart_metrics
WHERE fact_revenue != mart_revenue
`);

assert("gold_fct_pedido_item_customer_referential_integrity").query((ctx) => `
SELECT CAST(f.pedido_id AS STRING) AS violation_key
FROM ${ctx.ref("fct_pedido_item")} AS f
LEFT JOIN ${ctx.ref("dim_cliente")} AS c
  ON c.cliente_id = f.cliente_id
WHERE f.cliente_id IS NULL OR c.cliente_id IS NULL
`);

assert("gold_fct_pedido_item_date_coverage").query((ctx) => `
SELECT CAST(f.data_pedido AS STRING) AS violation_key
FROM ${ctx.ref("fct_pedido_item")} AS f
LEFT JOIN ${ctx.ref("dim_tempo")} AS t
  ON t.data = f.data_pedido
WHERE f.data_pedido IS NULL OR t.data_key IS NULL
GROUP BY violation_key
`);

assert("gold_dim_produto_sku_hierarchy_integrity").query((ctx) => `
SELECT CAST(variante_id AS STRING) AS violation_key
FROM ${ctx.ref("dim_produto_sku")}
WHERE variante_id IS NULL
   OR produto_id IS NULL
   OR marca_id IS NULL
   OR categoria_id IS NULL
`);

assert("gold_mart_catalogo_reconciliado_grain").query((ctx) => `
SELECT catalog_key
FROM ${ctx.ref("mart_catalogo_reconciliado")}
WHERE catalog_key IS NULL OR TRIM(catalog_key) = ''

UNION ALL

SELECT catalog_key
FROM ${ctx.ref("mart_catalogo_reconciliado")}
GROUP BY catalog_key
HAVING COUNT(*) > 1
`);

assert("gold_mart_catalogo_reconciliado_source_flags").query((ctx) => `
SELECT catalog_key
FROM ${ctx.ref("mart_catalogo_reconciliado")}
WHERE CAST(has_postgres AS INT64)
    + CAST(has_api AS INT64)
    + CAST(has_supplier AS INT64) < 1
`);

assert("gold_mart_catalogo_reconciliado_status").query((ctx) => `
SELECT catalog_key
FROM ${ctx.ref("mart_catalogo_reconciliado")}
WHERE match_status NOT IN (
  'all_sources',
  'postgres_and_api',
  'postgres_and_supplier',
  'api_and_supplier',
  'postgres_only',
  'api_only',
  'supplier_only'
)
`);
