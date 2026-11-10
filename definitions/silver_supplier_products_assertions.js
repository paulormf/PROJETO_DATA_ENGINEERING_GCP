assert("silver_supplier_products_quality").query((ctx) => `
SELECT sku AS violation_key
FROM ${ctx.ref("silver_supplier_products")}
WHERE sku IS NULL
   OR TRIM(sku) = ''
   OR product_name IS NULL
   OR TRIM(product_name) = ''
   OR category IS NULL
   OR TRIM(category) = ''
   OR price < 0
   OR stock_quantity < 0
`);

assert("silver_supplier_products_unique_sku").query((ctx) => `
SELECT sku
FROM ${ctx.ref("silver_supplier_products")}
GROUP BY sku
HAVING COUNT(*) > 1
`);

assert("silver_supplier_products_metadata_integrity").query((ctx) => `
SELECT sku AS violation_key
FROM ${ctx.ref("silver_supplier_products")}
WHERE source_system IS NULL
   OR batch_id IS NULL
   OR _ingested_at IS NULL
   OR record_hash IS NULL
`);

assert("silver_supplier_products_source_timestamp").query((ctx) => `
SELECT sku AS violation_key
FROM ${ctx.ref("silver_supplier_products")}
WHERE source_updated_at IS NOT NULL
  AND source_updated_at > CURRENT_TIMESTAMP()
`);
