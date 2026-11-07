-- Descoberta somente leitura para o catalogo de ingestao.
-- Execute no PostgreSQL de origem conectado ao banco appdb.

-- 1. Chaves primarias e ordem das colunas.
SELECT
    n.nspname AS table_schema,
    c.relname AS table_name,
    con.conname AS constraint_name,
    k.ordinality AS column_position,
    a.attname AS column_name,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type
FROM pg_constraint con
JOIN pg_class c
  ON c.oid = con.conrelid
JOIN pg_namespace n
  ON n.oid = c.relnamespace
JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ordinality)
  ON TRUE
JOIN pg_attribute a
  ON a.attrelid = c.oid
 AND a.attnum = k.attnum
WHERE con.contype = 'p'
  AND n.nspname = 'ecommerce'
ORDER BY table_name, column_position;

-- 2. Foreign keys e correspondencia entre origem e destino.
SELECT
    source_ns.nspname AS source_schema,
    source_table.relname AS source_table,
    source_con.conname AS constraint_name,
    source_col.ordinality AS column_position,
    source_attr.attname AS source_column,
    target_ns.nspname AS target_schema,
    target_table.relname AS target_table,
    target_attr.attname AS target_column
FROM pg_constraint source_con
JOIN pg_class source_table
  ON source_table.oid = source_con.conrelid
JOIN pg_namespace source_ns
  ON source_ns.oid = source_table.relnamespace
JOIN pg_class target_table
  ON target_table.oid = source_con.confrelid
JOIN pg_namespace target_ns
  ON target_ns.oid = target_table.relnamespace
JOIN LATERAL unnest(source_con.conkey) WITH ORDINALITY AS source_col(attnum, ordinality)
  ON TRUE
JOIN LATERAL unnest(source_con.confkey) WITH ORDINALITY AS target_col(attnum, ordinality)
  ON target_col.ordinality = source_col.ordinality
JOIN pg_attribute source_attr
  ON source_attr.attrelid = source_table.oid
 AND source_attr.attnum = source_col.attnum
JOIN pg_attribute target_attr
  ON target_attr.attrelid = target_table.oid
 AND target_attr.attnum = target_col.attnum
WHERE source_con.contype = 'f'
  AND source_ns.nspname = 'ecommerce'
ORDER BY source_table, constraint_name, column_position;

-- 3. Colunas candidatas a watermark incremental.
-- O resultado e candidato tecnico; a estrategia final exige confirmar
-- semantica de atualizacao e comportamento de deletes.
SELECT
    table_schema,
    table_name,
    ordinal_position,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'ecommerce'
  AND (
      lower(column_name) LIKE '%criad%'
      OR lower(column_name) LIKE '%atualiz%'
      OR lower(column_name) LIKE '%created%'
      OR lower(column_name) LIKE '%updated%'
      OR lower(column_name) LIKE '%deleted%'
      OR lower(column_name) LIKE '%exclu%'
  )
ORDER BY table_name, ordinal_position;

-- 4. Chaves unicas declaradas, incluindo indices unicos.
SELECT
    n.nspname AS table_schema,
    c.relname AS table_name,
    i.relname AS index_name,
    ix.indisprimary AS is_primary,
    ix.indisunique AS is_unique,
    pg_get_indexdef(ix.indexrelid) AS index_definition
FROM pg_index ix
JOIN pg_class c
  ON c.oid = ix.indrelid
JOIN pg_class i
  ON i.oid = ix.indexrelid
JOIN pg_namespace n
  ON n.oid = c.relnamespace
WHERE n.nspname = 'ecommerce'
  AND ix.indisunique
ORDER BY table_name, index_name;
