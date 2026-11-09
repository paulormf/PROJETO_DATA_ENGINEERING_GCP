output "github_actions_service_account_email" {
  description = "Service account usada pelo workflow de imagens Cloud Run."
  value       = google_service_account.deployer.email
}

output "workload_identity_provider" {
  description = "Identificador completo usado em GCP_WIF_PROVIDER no GitHub."
  value       = "${data.google_iam_workload_identity_pool.github_actions.name}/providers/${var.workload_identity_provider_id}"
}

output "artifact_registry_repository" {
  description = "Repositorio de imagens usado pelo pipeline."
  value       = data.google_artifact_registry_repository.images.name
}

output "github_environment_variables" {
  description = "Valores esperados no ambiente cloud-run-lab do GitHub."
  value = {
    GCP_PROJECT_ID               = var.project_id
    GCP_WIF_PROVIDER             = "${data.google_iam_workload_identity_pool.github_actions.name}/providers/${var.workload_identity_provider_id}"
    GCP_DEPLOYER_SERVICE_ACCOUNT = google_service_account.deployer.email
    ARTIFACT_REGISTRY_LOCATION   = var.artifact_registry_location
    ARTIFACT_REGISTRY_REPOSITORY = var.artifact_registry_repository
    CLOUD_RUN_REGION             = var.region
    FULL_EXTRACT_JOB_NAME        = "ecommerce-full-extract"
    MATERIALIZER_JOB_NAME        = "ecommerce-bronze-materializer"
  }
}
