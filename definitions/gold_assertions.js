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
