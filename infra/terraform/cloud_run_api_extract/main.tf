data "google_storage_bucket" "bronze" {
  name    = var.bucket_name
  project = var.project_id
}

resource "google_service_account" "api_extract" {
  account_id   = var.service_account_id
  display_name = "Data Engineering API extraction writer"
  description  = "Extrai a API publica e grava objetos Raw no Cloud Storage."
  project      = var.project_id
}

resource "google_storage_bucket_iam_member" "api_extract_object_creator" {
  bucket = data.google_storage_bucket.bronze.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.api_extract.email}"
}

resource "google_project_iam_member" "api_extract_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.api_extract.email}"
}

resource "google_cloud_run_v2_job" "api_extract" {
  name     = var.job_name
  location = var.region
  project  = var.project_id

  labels = {
    environment = "lab"
    component   = "api-extract"
    layer       = "bronze"
    managed_by  = "terraform"
  }

  lifecycle {
    # O GitHub Actions atualiza somente o digest da imagem.
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }

  template {
    template {
      service_account = google_service_account.api_extract.email
      max_retries     = var.max_retries
      timeout         = var.task_timeout

      containers {
        image = var.api_extract_image
        args  = var.job_default_args

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }

        resources {
          limits = {
            cpu    = var.cpu_limit
            memory = var.memory_limit
          }
        }
      }
    }
  }
}
