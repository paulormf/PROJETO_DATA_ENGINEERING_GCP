data "google_iam_workload_identity_pool" "github_actions" {
  provider                  = google-beta
  project                   = var.project_id
  workload_identity_pool_id = var.workload_identity_pool_id
}

resource "google_iam_workload_identity_pool_provider" "repository" {
  provider                           = google-beta
  project                            = var.project_id
  workload_identity_pool_id          = var.workload_identity_pool_id
  workload_identity_pool_provider_id = var.workload_identity_provider_id
  display_name                       = "GitHub OIDC - Composer DAGs"
  description                        = "Federacao restrita ao repositorio de DAGs Composer."

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/main'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  account_id   = var.deployer_service_account_id
  display_name = "GitHub Actions Composer DAG deployer"
  description  = "Publica somente os arquivos versionados das DAGs no bucket do Composer."
  project      = var.project_id
}

resource "google_service_account_iam_member" "github_actions_workload_identity_user" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${data.google_iam_workload_identity_pool.github_actions.name}/attribute.repository/${var.github_repository}"
}

resource "google_storage_bucket_iam_member" "composer_dags_object_user" {
  bucket = var.composer_dags_bucket
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.deployer.email}"
}
