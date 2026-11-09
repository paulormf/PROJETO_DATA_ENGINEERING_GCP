data "google_storage_bucket" "bronze" {
  name    = var.bucket_name
  project = var.project_id
}

resource "google_service_account" "materializer" {
  account_id   = var.materializer_service_account_id
  display_name = "Data Engineering BigQuery Bronze materializer"
  project      = var.project_id
}

resource "google_storage_bucket_iam_member" "materializer_object_viewer" {
  bucket = data.google_storage_bucket.bronze.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.materializer.email}"
}

resource "google_project_iam_member" "materializer_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.materializer.email}"
}

resource "google_bigquery_dataset_iam_member" "materializer_data_editor" {
  project    = var.project_id
  dataset_id = var.bronze_dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.materializer.email}"
}
