assert("silver_dummyjson_products_quality").query((ctx) => `
SELECT CAST(product_id AS STRING) AS violation_key
FROM ${ctx.ref("silver_dummyjson_products")}
WHERE product_id IS NULL
   OR title IS NULL
   OR TRIM(title) = ''
   OR category IS NULL
   OR TRIM(category) = ''
   OR price < 0
   OR stock < 0
   OR (discount_percentage IS NOT NULL AND discount_percentage < 0)
   OR (rating IS NOT NULL AND (rating < 0 OR rating > 5))
   OR (weight IS NOT NULL AND weight < 0)
   OR (minimum_order_quantity IS NOT NULL AND minimum_order_quantity < 0)
`);

assert("silver_dummyjson_products_unique_product_id").query((ctx) => `
SELECT product_id
FROM ${ctx.ref("silver_dummyjson_products")}
GROUP BY product_id
HAVING COUNT(*) > 1
`);

assert("silver_dummyjson_products_metadata_integrity").query((ctx) => `
SELECT CAST(product_id AS STRING) AS violation_key
FROM ${ctx.ref("silver_dummyjson_products")}
WHERE source_system IS NULL
   OR batch_id IS NULL
   OR _ingested_at IS NULL
   OR source_extracted_at IS NULL
   OR record_hash IS NULL
`);
