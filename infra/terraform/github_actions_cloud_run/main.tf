data "google_iam_workload_identity_pool" "github_actions" {
  provider                  = google-beta
  project                   = var.project_id
  workload_identity_pool_id = var.workload_identity_pool_id
}

data "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.artifact_registry_location
  repository_id = var.artifact_registry_repository
}

data "google_service_account" "runtime" {
  for_each   = var.runtime_service_account_ids
  project    = var.project_id
  account_id = each.value
}

resource "google_service_account" "deployer" {
  account_id   = var.deployer_service_account_id
  display_name = "GitHub Actions Cloud Run image deployer"
  description  = "Publica imagens e atualiza somente os Jobs Cloud Run do projeto."
  project      = var.project_id
}

resource "google_service_account_iam_member" "github_actions_workload_identity_user" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${data.google_iam_workload_identity_pool.github_actions.name}/attribute.repository/${var.github_repository}"
}

resource "google_artifact_registry_repository_iam_member" "image_writer" {
  project    = var.project_id
  location   = data.google_artifact_registry_repository.images.location
  repository = data.google_artifact_registry_repository.images.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "cloud_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "runtime_service_account_user" {
  for_each           = data.google_service_account.runtime
  service_account_id = each.value.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
