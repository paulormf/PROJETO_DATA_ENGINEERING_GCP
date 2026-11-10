const action = publish("silver_supplier_products", {
  type: "incremental",
  tags: ["silver", "supplier", "csv"],
  description:
    "Estado atual dos produtos recebidos do fornecedor CSV e processados pelo Dataflow Batch.",
  uniqueKey: ["sku"],
  bigquery: {
    partitionBy: "DATE(_ingested_at)",
    clusterBy: ["sku", "category"],
  },
  columns: {
    sku: "Chave comercial usada para reconciliacao entre fontes.",
    record_hash: "Hash SHA-256 do registro normalizado do fornecedor.",
    _ingested_at: "Timestamp de ingestao do lote no Bronze.",
    source_updated_at: "Timestamp informado pelo fornecedor, quando disponivel.",
  },
});

action.preOps((ctx) => `
DECLARE source_checkpoint TIMESTAMP DEFAULT (
  ${ctx.when(
    ctx.incremental(),
    `SELECT COALESCE(
       TIMESTAMP_SUB(MAX(_ingested_at), INTERVAL 1 DAY),
       TIMESTAMP('1970-01-01')
     )
     FROM ${ctx.self()}`,
    `SELECT TIMESTAMP('1970-01-01')`,
  )}
);
`);

action.query((ctx) => `
WITH candidates AS (
  SELECT
    source_system,
    batch_id,
    ingested_at AS _ingested_at,
    record_hash,
    TRIM(supplier_product_id) AS supplier_product_id,
    TRIM(sku) AS sku,
    TRIM(product_name) AS product_name,
    TRIM(category) AS category,
    NULLIF(TRIM(brand), '') AS brand,
    price,
    stock_quantity,
    source_updated_at
  FROM ${ctx.ref("supplier_products_raw")}
  WHERE ingested_at >= source_checkpoint
), ranked AS (
  SELECT
    candidates.*,
    ROW_NUMBER() OVER (
      PARTITION BY sku
      ORDER BY
        source_updated_at DESC NULLS LAST,
        _ingested_at DESC,
        batch_id DESC,
        record_hash DESC
    ) AS _row_number
  FROM candidates
)
SELECT * EXCEPT (_row_number)
FROM ranked
WHERE _row_number = 1
`);
