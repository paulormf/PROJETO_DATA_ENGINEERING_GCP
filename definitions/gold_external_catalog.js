const catalog = publish("mart_catalogo_reconciliado", {
  type: "table",
  schema: "ecommerce_gold",
  tags: ["gold", "mart", "multi-source", "catalog"],
  description:
    "Catalogo reconciliado entre PostgreSQL, API DummyJSON e fornecedor CSV.",
  bigquery: {
    clusterBy: ["match_status", "catalog_key"],
  },
});

catalog.query((ctx) => `
WITH postgres_products AS (
  SELECT
    COALESCE(
      NULLIF(LOWER(TRIM(sku)), ''),
      CONCAT('postgres-variant:', CAST(variante_id AS STRING))
    ) AS catalog_key,
    sku,
    CAST(NULL AS INT64) AS api_product_id,
    CAST(NULL AS STRING) AS supplier_product_id,
    variante_id,
    produto_id,
    nome_produto,
    CAST(NULL AS STRING) AS supplier_product_name,
    CAST(NULL AS STRING) AS api_title,
    nome_produto AS postgres_product_name,
    CAST(NULL AS STRING) AS api_category,
    CAST(NULL AS STRING) AS supplier_category,
    nome_categoria AS postgres_category,
    CAST(NULL AS NUMERIC) AS api_price,
    CAST(NULL AS NUMERIC) AS supplier_price,
    preco_venda AS postgres_price,
    _silver_ingested_at
  FROM ${ctx.ref("dim_produto_sku")}
  WHERE sku IS NOT NULL
), api_products AS (
  SELECT
    COALESCE(
      NULLIF(LOWER(TRIM(sku)), ''),
      CONCAT('api-product:', CAST(product_id AS STRING))
    ) AS catalog_key,
    sku,
    product_id AS api_product_id,
    CAST(NULL AS STRING) AS supplier_product_id,
    CAST(NULL AS INT64) AS variante_id,
    CAST(NULL AS INT64) AS produto_id,
    CAST(NULL AS STRING) AS nome_produto,
    CAST(NULL AS STRING) AS supplier_product_name,
    title AS api_title,
    CAST(NULL AS STRING) AS postgres_product_name,
    category AS api_category,
    CAST(NULL AS STRING) AS supplier_category,
    CAST(NULL AS STRING) AS postgres_category,
    price AS api_price,
    CAST(NULL AS NUMERIC) AS supplier_price,
    CAST(NULL AS NUMERIC) AS postgres_price,
    _ingested_at AS _silver_ingested_at
  FROM ${ctx.ref("silver_dummyjson_products")}
), supplier_products AS (
  SELECT
    COALESCE(
      NULLIF(LOWER(TRIM(sku)), ''),
      CONCAT('supplier-product:', CAST(supplier_product_id AS STRING))
    ) AS catalog_key,
    sku,
    CAST(NULL AS INT64) AS api_product_id,
    supplier_product_id,
    CAST(NULL AS INT64) AS variante_id,
    CAST(NULL AS INT64) AS produto_id,
    CAST(NULL AS STRING) AS nome_produto,
    product_name AS supplier_product_name,
    CAST(NULL AS STRING) AS api_title,
    CAST(NULL AS STRING) AS postgres_product_name,
    CAST(NULL AS STRING) AS api_category,
    category AS supplier_category,
    CAST(NULL AS STRING) AS postgres_category,
    CAST(NULL AS NUMERIC) AS api_price,
    price AS supplier_price,
    CAST(NULL AS NUMERIC) AS postgres_price,
    _ingested_at AS _silver_ingested_at
  FROM ${ctx.ref("silver_supplier_products")}
), joined AS (
  SELECT
    COALESCE(p.catalog_key, a.catalog_key, s.catalog_key) AS catalog_key,
    COALESCE(p.sku, a.sku, s.sku) AS sku,
    p.variante_id,
    p.produto_id,
    a.api_product_id,
    s.supplier_product_id,
    COALESCE(p.nome_produto, a.api_title, s.supplier_product_name) AS canonical_product_name,
    COALESCE(p.postgres_category, a.api_category, s.supplier_category) AS canonical_category,
    p.nome_produto AS postgres_product_name,
    a.api_title,
    s.supplier_product_name,
    p.postgres_category,
    a.api_category,
    s.supplier_category,
    p.postgres_price,
    a.api_price,
    s.supplier_price,
    CASE
      WHEN p.catalog_key IS NOT NULL
       AND a.catalog_key IS NOT NULL
       AND s.catalog_key IS NOT NULL THEN 'all_sources'
      WHEN p.catalog_key IS NOT NULL AND a.catalog_key IS NOT NULL THEN 'postgres_and_api'
      WHEN p.catalog_key IS NOT NULL AND s.catalog_key IS NOT NULL THEN 'postgres_and_supplier'
      WHEN a.catalog_key IS NOT NULL AND s.catalog_key IS NOT NULL THEN 'api_and_supplier'
      WHEN p.catalog_key IS NOT NULL THEN 'postgres_only'
      WHEN a.catalog_key IS NOT NULL THEN 'api_only'
      ELSE 'supplier_only'
    END AS match_status,
    p.catalog_key IS NOT NULL AS has_postgres,
    a.catalog_key IS NOT NULL AS has_api,
    s.catalog_key IS NOT NULL AS has_supplier,
    s.supplier_price - a.api_price AS supplier_api_price_difference,
    GREATEST(
      COALESCE(p._silver_ingested_at, TIMESTAMP('1970-01-01')),
      COALESCE(a._silver_ingested_at, TIMESTAMP('1970-01-01')),
      COALESCE(s._silver_ingested_at, TIMESTAMP('1970-01-01'))
    ) AS _silver_ingested_at
  FROM postgres_products AS p
  FULL OUTER JOIN api_products AS a
    ON p.catalog_key = a.catalog_key
  FULL OUTER JOIN supplier_products AS s
    ON COALESCE(p.catalog_key, a.catalog_key) = s.catalog_key
)
SELECT *
FROM joined
`);
