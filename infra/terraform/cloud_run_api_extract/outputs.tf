output "job_name" {
  description = "Nome do Cloud Run Job do extrator API."
  value       = google_cloud_run_v2_job.api_extract.name
}

output "service_account_email" {
  description = "Identidade usada pelo Cloud Run Job."
  value       = google_service_account.api_extract.email
}

output "job_uri" {
  description = "Nome totalmente qualificado do Job."
  value       = google_cloud_run_v2_job.api_extract.name
}
