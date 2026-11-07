resource "google_secret_manager_secret" "postgres" {
  for_each  = var.secret_ids
  secret_id = each.value
  project   = var.project_id

  replication {
    auto {}
  }

  labels = {
    environment = "lab"
    component   = "full-extract"
    managed_by  = "terraform"
  }
}

resource "google_secret_manager_secret_iam_member" "postgres_accessor" {
  for_each  = google_secret_manager_secret.postgres
  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.ingestion_service_account_email}"
}
