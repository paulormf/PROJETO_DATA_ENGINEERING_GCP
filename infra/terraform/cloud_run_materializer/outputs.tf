output "materializer_service_account_email" {
  description = "Service account que sera usada pelo job de materializacao."
  value       = google_service_account.materializer.email
}

output "bronze_bucket_name" {
  description = "Bucket lido pelo materializer."
  value       = data.google_storage_bucket.bronze.name
}

output "bronze_dataset_id" {
  description = "Dataset que recebe a permissao de escrita do materializer."
  value       = var.bronze_dataset_id
}
