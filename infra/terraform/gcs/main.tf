resource "google_storage_bucket" "bronze" {
  name                        = var.bucket_name
  location                    = var.region
  project                     = var.project_id
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = var.bucket_labels

  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_delete_age_days == null ? [] : [var.lifecycle_delete_age_days]
    content {
      condition {
        age = lifecycle_rule.value
      }
      action {
        type = "Delete"
      }
    }
  }
}

resource "google_service_account" "ingestion_writer" {
  account_id   = var.ingestion_service_account_id
  display_name = "Data Engineering Bronze ingestion writer"
  project      = var.project_id
}

resource "google_storage_bucket_iam_member" "ingestion_object_creator" {
  bucket = google_storage_bucket.bronze.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.ingestion_writer.email}"
}
