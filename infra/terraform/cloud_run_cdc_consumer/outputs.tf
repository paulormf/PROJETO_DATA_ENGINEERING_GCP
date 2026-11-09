output "consumer_service_account_email" {
  description = "Service account usada pelo consumidor CDC para gravar no BigQuery."
  value       = google_service_account.consumer.email
}

output "push_invoker_service_account_email" {
  description = "Service account usada pelo Pub/Sub para autenticar o push."
  value       = google_service_account.push_invoker.email
}

output "cdc_table_id" {
  description = "Tabela central append-only dos eventos CDC."
  value       = "${var.project_id}.${var.bronze_dataset_id}.${google_bigquery_table.cdc_events.table_id}"
}

output "consumer_service_name" {
  description = "Nome do servico Cloud Run do consumidor CDC."
  value       = google_cloud_run_v2_service.consumer.name
}

output "consumer_service_uri" {
  description = "URL privada/logica do servico Cloud Run usada pelo push Pub/Sub."
  value       = google_cloud_run_v2_service.consumer.uri
}

output "push_subscription_names" {
  description = "Assinaturas push criadas, uma por tabela de origem."
  value       = { for table, subscription in google_pubsub_subscription.push : table => subscription.name }
}
