output "github_actions_service_account_email" {
  description = "Service account usada pelo workflow de deploy."
  value       = google_service_account.deployer.email
}

output "workload_identity_provider" {
  description = "Identificador completo usado em GCP_WIF_PROVIDER no GitHub."
  value       = google_iam_workload_identity_pool_provider.repository.name
}

output "github_environment_variables" {
  description = "Valores esperados como variaveis do ambiente composer-lab no GitHub."
  value = {
    GCP_PROJECT_ID               = var.project_id
    GCP_WIF_PROVIDER             = google_iam_workload_identity_pool_provider.repository.name
    GCP_DEPLOYER_SERVICE_ACCOUNT = google_service_account.deployer.email
    COMPOSER_DAGS_BUCKET         = var.composer_dags_bucket
  }
}
