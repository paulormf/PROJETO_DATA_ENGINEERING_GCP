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

resource "google_cloud_run_v2_job" "materializer" {
  name     = var.job_name
  location = var.region
  project  = var.project_id

  labels = {
    environment = "lab"
    component   = "bronze-materializer"
    managed_by  = "terraform"
  }

  lifecycle {
    # O CI/CD atualiza somente o digest da imagem. Terraform continua sendo a
    # fonte de verdade para identidade, recursos, env e args do Job.
    ignore_changes = [
      template[0].template[0].containers[0].image,
    ]
  }

  template {
    template {
      service_account = google_service_account.materializer.email
      max_retries     = var.max_retries
      timeout         = var.task_timeout

      containers {
        image = var.materializer_image
        args  = var.job_default_args

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "GCS_BUCKET"
          value = var.bucket_name
        }

        env {
          name  = "BQ_BRONZE_DATASET"
          value = var.bronze_dataset_id
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
