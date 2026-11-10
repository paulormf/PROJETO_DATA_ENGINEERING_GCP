const { tables } = require("includes/table_catalog.js");

tables.forEach((table) => {
  declare({
    database: dataform.projectConfig.defaultDatabase,
    schema: "ecommerce_bronze",
    name: `bronze_${table.name}`,
  });
});

declare({
  database: dataform.projectConfig.defaultDatabase,
  schema: "ecommerce_bronze",
  name: "cdc_events_raw",
});

declare({
  database: dataform.projectConfig.defaultDatabase,
  schema: "ecommerce_bronze",
  name: "dummyjson_products_raw",
});

declare({
  database: dataform.projectConfig.defaultDatabase,
  schema: "ecommerce_bronze",
  name: "supplier_products_raw",
});
