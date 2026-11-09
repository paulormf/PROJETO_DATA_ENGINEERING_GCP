const { tables } = require("includes/table_catalog.js");

function quoteIdentifier(name) {
  return `\`${name}\``;
}

tables.forEach((table) => {
  const silverName = `silver_${table.name}`;
  const keyColumns = table.primaryKey.map(quoteIdentifier).join(", ");
  const nullPredicate = table.primaryKey
    .map((column) => `${quoteIdentifier(column)} IS NULL`)
    .join(" OR ");

  assert(`${silverName}_primary_key_integrity`).query((ctx) => `
SELECT ${keyColumns}
FROM ${ctx.ref(silverName)}
WHERE ${nullPredicate}

UNION ALL

SELECT ${keyColumns}
FROM ${ctx.ref(silverName)}
GROUP BY ${keyColumns}
HAVING COUNT(*) > 1
`);
});
