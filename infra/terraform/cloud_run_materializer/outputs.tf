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

output "materializer_job_name" {
  description = "Nome do Cloud Run Job de materializacao."
  value       = google_cloud_run_v2_job.materializer.name
}

output "materializer_job_id" {
  description = "Identificador do Cloud Run Job de materializacao."
  value       = google_cloud_run_v2_job.materializer.id
}
