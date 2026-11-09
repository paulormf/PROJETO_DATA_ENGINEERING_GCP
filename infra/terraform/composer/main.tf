resource "google_service_account" "composer" {
  account_id   = var.composer_service_account_id
  display_name = "Data Engineering Composer orchestrator"
  project      = var.project_id
}

resource "google_project_iam_member" "composer_worker" {
  project = var.project_id
  role    = "roles/composer.worker"
  member  = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_cloud_run_v2_job_iam_member" "materializer_executor" {
  project  = var.project_id
  location = var.region
  name     = var.materializer_job_name
  role     = "roles/run.jobsExecutorWithOverrides"
  member   = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_cloud_run_v2_job_iam_member" "materializer_viewer" {
  project  = var.project_id
  location = var.region
  name     = var.materializer_job_name
  role     = "roles/run.viewer"
  member   = "serviceAccount:${google_service_account.composer.email}"
}

resource "google_composer_environment" "composer" {
  provider = google-beta
  name     = var.environment_name
  region   = var.region
  labels   = var.labels

  config {
    software_config {
      image_version = var.image_version
    }

    node_config {
      service_account = google_service_account.composer.email
    }
  }

  depends_on = [google_project_iam_member.composer_worker]
}
