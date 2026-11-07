output "bronze_bucket_name" {
  description = "Nome do bucket Bronze criado."
  value       = google_storage_bucket.bronze.name
}

output "bronze_bucket_url" {
  description = "URI gs:// do bucket Bronze."
  value       = "gs://${google_storage_bucket.bronze.name}"
}

output "ingestion_service_account_email" {
  description = "Email da service account de escrita da ingestao."
  value       = google_service_account.ingestion_writer.email
}
