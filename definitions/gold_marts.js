const martVendasDiarias = publish("mart_vendas_diarias", {
  type: "table",
  schema: "ecommerce_gold",
  tags: ["gold", "mart", "sales"],
  description: "Data mart diario de vendas por canal, moeda e categoria.",
  bigquery: {
    partitionBy: "data_pedido",
    clusterBy: ["canal_venda", "categoria_id"],
  },
});

martVendasDiarias.query((ctx) => `
SELECT
  f.data_pedido,
  t.data_key,
  t.ano,
  t.mes,
  f.canal_venda,
  f.moeda,
  f.categoria_id,
  COUNT(DISTINCT f.pedido_id) AS quantidade_pedidos,
  COUNT(*) AS quantidade_itens,
  SUM(f.quantidade) AS quantidade_unidades,
  SUM(f.total_item) AS receita_itens,
  SUM(f.desconto_item) AS desconto_itens
FROM ${ctx.ref("fct_pedido_item")} AS f
LEFT JOIN ${ctx.ref("dim_tempo")} AS t
  ON t.data = f.data_pedido
GROUP BY
  f.data_pedido,
  t.data_key,
  t.ano,
  t.mes,
  f.canal_venda,
  f.moeda,
  f.categoria_id
`);
