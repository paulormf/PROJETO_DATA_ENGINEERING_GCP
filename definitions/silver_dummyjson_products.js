const action = publish("silver_dummyjson_products", {
  type: "incremental",
  tags: ["silver", "api", "dummyjson"],
  description:
    "Current-state Silver model for DummyJSON products loaded by the API and Dataflow Batch pipeline.",
  uniqueKey: ["product_id"],
  bigquery: {
    partitionBy: "DATE(_ingested_at)",
    clusterBy: ["category", "product_id"],
  },
  columns: {
    product_id: "Business key from the DummyJSON product source.",
    record_hash: "SHA-256 hash of the canonical source product payload.",
    _ingested_at: "Timestamp when the API batch was loaded into Bronze.",
    source_updated_at:
      "Timestamp reported by the source, when available, used for latest-state selection.",
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
    source_extracted_at,
    record_hash,
    product_id,
    title,
    description,
    category,
    price,
    discount_percentage,
    rating,
    stock,
    brand,
    sku,
    weight,
    availability_status,
    minimum_order_quantity,
    source_created_at,
    source_updated_at,
    tags_json,
    images_json,
    thumbnail
  FROM ${ctx.ref("dummyjson_products_raw")}
  WHERE ingested_at >= source_checkpoint
), ranked AS (
  SELECT
    candidates.*,
    ROW_NUMBER() OVER (
      PARTITION BY product_id
      ORDER BY
        source_updated_at DESC NULLS LAST,
        source_created_at DESC NULLS LAST,
        source_extracted_at DESC,
        _ingested_at DESC,
        batch_id DESC
    ) AS _row_number
  FROM candidates
)
SELECT * EXCEPT (_row_number)
FROM ranked
WHERE _row_number = 1
`);
