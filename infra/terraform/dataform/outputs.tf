output "silver_dataset_id" {
  description = "ID do dataset Silver."
  value       = google_bigquery_dataset.silver.dataset_id
}

output "gold_dataset_id" {
  description = "ID do dataset Gold."
  value       = google_bigquery_dataset.gold.dataset_id
}

output "assertion_dataset_id" {
  description = "ID do dataset de assertions."
  value       = google_bigquery_dataset.assertions.dataset_id
}

output "dataform_repository_name" {
  description = "Nome completo do repositorio Dataform."
  value       = google_dataform_repository.ecommerce.name
}

output "dataform_service_account_email" {
  description = "Service account usada para executar os workflows Dataform."
  value       = google_service_account.dataform_runner.email
}
