output "composer_environment_name" {
  description = "Nome do ambiente Composer criado pelo modulo."
  value       = google_composer_environment.composer.name
}

output "composer_service_account_email" {
  description = "Service account usada pelos componentes do Composer."
  value       = google_service_account.composer.email
}

output "materializer_job_name" {
  description = "Cloud Run Job autorizado para execucao pela DAG."
  value       = var.materializer_job_name
}
