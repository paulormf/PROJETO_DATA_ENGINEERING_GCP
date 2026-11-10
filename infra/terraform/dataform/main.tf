data "google_project" "current" {
  project_id = var.project_id
}

locals {
  labels = {
    environment = "lab"
    domain      = "ecommerce"
    managed_by  = "terraform"
    component   = "dataform"
  }

  dataform_service_agent = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-dataform.iam.gserviceaccount.com"
}

resource "google_project_service" "dataform_api" {
  project            = var.project_id
  service            = "dataform.googleapis.com"
  disable_on_destroy = false
}

resource "google_bigquery_dataset" "silver" {
  project                    = var.project_id
  dataset_id                 = var.silver_dataset_id
  location                   = var.bigquery_location
  description                = "Camada Silver incremental do dominio ecommerce."
  delete_contents_on_destroy = false
  labels                     = merge(local.labels, { layer = "silver" })
}

resource "google_bigquery_dataset" "gold" {
  project                    = var.project_id
  dataset_id                 = var.gold_dataset_id
  location                   = var.bigquery_location
  description                = "Camada Gold dimensional e data marts do dominio ecommerce."
  delete_contents_on_destroy = false
  labels                     = merge(local.labels, { layer = "gold" })
}

resource "google_bigquery_dataset" "assertions" {
  project                    = var.project_id
  dataset_id                 = var.assertion_dataset_id
  location                   = var.bigquery_location
  description                = "Resultados das assertions de qualidade do Dataform."
  delete_contents_on_destroy = false
  labels                     = merge(local.labels, { layer = "quality" })
}

resource "google_service_account" "dataform_runner" {
  project      = var.project_id
  account_id   = var.dataform_service_account_id
  display_name = "Data Engineering Dataform runner"
  description  = "Identidade de menor privilegio para executar workflows Dataform."
}

resource "google_bigquery_dataset_iam_member" "runner_bronze_viewer" {
  project    = var.project_id
  dataset_id = var.bronze_dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.dataform_runner.email}"
}

resource "google_bigquery_dataset_iam_member" "runner_silver_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.silver.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dataform_runner.email}"
}

resource "google_bigquery_dataset_iam_member" "runner_gold_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.gold.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dataform_runner.email}"
}

resource "google_bigquery_dataset_iam_member" "runner_assertions_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.assertions.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dataform_runner.email}"
}

resource "google_project_iam_member" "runner_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dataform_runner.email}"
}

resource "google_service_account_iam_member" "dataform_service_agent_user" {
  service_account_id = google_service_account.dataform_runner.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.dataform_service_agent
}

resource "google_service_account_iam_member" "dataform_service_agent_token_creator" {
  service_account_id = google_service_account.dataform_runner.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.dataform_service_agent
}

resource "google_dataform_repository" "ecommerce" {
  provider = google-beta

  project         = var.project_id
  region          = var.dataform_region
  name            = var.dataform_repository_id
  display_name    = var.dataform_repository_display_name
  service_account = google_service_account.dataform_runner.email
  labels          = local.labels

  git_remote_settings {
    url                 = var.dataform_git_repository_url
    default_branch      = var.dataform_git_default_branch
    git_repository_link = var.dataform_git_repository_link
  }

  depends_on = [
    google_project_service.dataform_api,
    google_service_account_iam_member.dataform_service_agent_user,
    google_service_account_iam_member.dataform_service_agent_token_creator,
  ]
}
