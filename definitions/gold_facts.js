const factPedidoItem = publish("fct_pedido_item", {
  type: "table",
  schema: "ecommerce_gold",
  tags: ["gold", "fact"],
  description: "Fato no grao de item de pedido, enriquecido com pedido e SKU.",
  bigquery: {
    partitionBy: "data_pedido",
    clusterBy: ["cliente_id", "variante_id", "canal_venda"],
  },
});

factPedidoItem.query((ctx) => `
SELECT
  i.item_pedido_id,
  i.pedido_id,
  p.cliente_id,
  i.variante_id,
  d.produto_id,
  d.marca_id,
  d.categoria_id,
  DATE(p.realizado_em) AS data_pedido,
  p.realizado_em,
  p.atualizado_em,
  p.status_pedido,
  p.canal_venda,
  p.moeda,
  i.quantidade,
  i.preco_unitario,
  i.desconto_total AS desconto_item,
  i.total_item,
  p.subtotal,
  p.desconto_total AS desconto_pedido,
  p.frete_total,
  p.total_pedido,
  GREATEST(i._ingested_at, p._ingested_at) AS _silver_ingested_at
FROM ${ctx.ref("silver_itens_pedido")} AS i
JOIN ${ctx.ref("silver_pedidos")} AS p
  ON p.pedido_id = i.pedido_id
  AND p._is_deleted = FALSE
LEFT JOIN ${ctx.ref("dim_produto_sku")} AS d
  ON d.variante_id = i.variante_id
WHERE i._is_deleted = FALSE
`);
