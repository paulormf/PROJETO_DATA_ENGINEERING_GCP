const { tables } = require("includes/table_catalog.js");

function quoteIdentifier(name) {
  return `\`${name}\``;
}

function jsonValue(column) {
  const payload = "CASE WHEN c.operation = 'd' THEN c.before_json ELSE c.after_json END";
  const path = `$.${column.name}`;

  if (column.jsonQuery) {
    return `JSON_QUERY(${payload}, '${path}') AS ${quoteIdentifier(column.name)}`;
  }

  if (column.type === "STRING") {
    return `JSON_VALUE(${payload}, '${path}') AS ${quoteIdentifier(column.name)}`;
  }

  return `SAFE_CAST(JSON_VALUE(${payload}, '${path}') AS ${column.type}) AS ${quoteIdentifier(column.name)}`;
}

tables.forEach((table) => {
  const silverName = `silver_${table.name}`;
  const bronzeName = `bronze_${table.name}`;
  const keyColumns = table.primaryKey.map(quoteIdentifier).join(", ");

  const baselineColumns = table.columns
    .map((column) => `b.${quoteIdentifier(column.name)} AS ${quoteIdentifier(column.name)}`)
    .join(",\n      ");

  const cdcColumns = table.columns.map(jsonValue).join(",\n      ");

  publish(silverName, {
    type: "incremental",
    uniqueKey: table.primaryKey,
    tags: ["silver", "postgresql", table.name],
    description: `Current-state Silver model for ecommerce.${table.name}, reconciled from the full Bronze baseline and Debezium CDC.`,
    bigquery: {
      partitionBy: "DATE(_ingested_at)",
      clusterBy: table.primaryKey,
    },
  }).query((ctx) => {
    // Keep the source partition filter directly on ingested_at. A dynamic
    // scalar subquery over the target table prevents BigQuery partition
    // elimination and makes the incremental query fail when the source table
    // requires a partition filter.
    const cdcLookbackDays = 7;
    const cdcLowerBound = ctx.when(
      ctx.incremental(),
      `TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL ${cdcLookbackDays} DAY)`,
      "TIMESTAMP('1970-01-01')",
    );

    return `
WITH candidates AS (
  SELECT
      ${baselineColumns},
      'r' AS _operation,
      CAST(NULL AS INT64) AS _source_lsn,
      FALSE AS _is_deleted,
      COALESCE(b._ingested_at, TIMESTAMP('1970-01-01')) AS _ingested_at
  FROM ${ctx.ref(bronzeName)} AS b
  ${ctx.when(ctx.incremental(), "WHERE FALSE")}

  UNION ALL

  SELECT
      ${cdcColumns},
      c.operation AS _operation,
      c.source_lsn AS _source_lsn,
      c.operation = 'd' AS _is_deleted,
      c.ingested_at AS _ingested_at
  FROM (
    SELECT *
    FROM ${ctx.ref("cdc_events_raw")}
    WHERE source_table = '${table.name}'
      AND ingested_at >= ${cdcLowerBound}
    QUALIFY ROW_NUMBER() OVER (
      PARTITION BY event_id
      ORDER BY ingested_at DESC
    ) = 1
  ) AS c
), ranked AS (
  SELECT
      candidates.*,
      ROW_NUMBER() OVER (
        PARTITION BY ${keyColumns}
        ORDER BY _source_lsn DESC NULLS LAST, _ingested_at DESC, _is_deleted DESC
      ) AS _row_number
  FROM candidates
)
SELECT * EXCEPT (_row_number)
FROM ranked
WHERE _row_number = 1
`;
  });
});
