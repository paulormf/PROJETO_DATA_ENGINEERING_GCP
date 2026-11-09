data "google_project" "current" {
  project_id = var.project_id
}

data "google_pubsub_topic" "cdc" {
  for_each = var.tables

  project = var.project_id
  name    = "${var.topic_prefix}.${var.source_schema}.${each.value}"
}

data "google_pubsub_topic" "dead_letter" {
  project = var.project_id
  name    = "${var.topic_prefix}.dead-letter"
}

locals {
  labels = {
    environment = "lab"
    component   = "cdc-consumer"
    layer       = "bronze"
    managed_by  = "terraform"
    pipeline    = "cdc"
  }

  pubsub_service_agent = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"

  cdc_schema = [
    { name = "event_id", type = "STRING", mode = "REQUIRED" },
    { name = "pubsub_message_id", type = "STRING", mode = "NULLABLE" },
    { name = "ordering_key", type = "STRING", mode = "NULLABLE" },
    { name = "source_schema", type = "STRING", mode = "REQUIRED" },
    { name = "source_table", type = "STRING", mode = "REQUIRED" },
    { name = "operation", type = "STRING", mode = "REQUIRED" },
    { name = "snapshot", type = "BOOL", mode = "REQUIRED" },
    { name = "source_lsn", type = "INT64", mode = "NULLABLE" },
    { name = "transaction_id", type = "INT64", mode = "NULLABLE" },
    { name = "before_json", type = "STRING", mode = "NULLABLE" },
    { name = "after_json", type = "STRING", mode = "NULLABLE" },
    { name = "raw_json", type = "STRING", mode = "REQUIRED" },
    { name = "ingested_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ]
}

resource "google_service_account" "consumer" {
  account_id   = var.consumer_service_account_id
  display_name = "Data Engineering CDC BigQuery consumer"
  description  = "Recebe eventos CDC do Pub/Sub e grava a tabela raw Bronze."
  project      = var.project_id
}

resource "google_service_account" "push_invoker" {
  account_id   = var.push_invoker_service_account_id
  display_name = "Data Engineering CDC Pub/Sub push invoker"
  description  = "Identidade usada pelo Pub/Sub para autenticar chamadas ao consumidor CDC."
  project      = var.project_id
}

resource "google_bigquery_table" "cdc_events" {
  project                  = var.project_id
  dataset_id               = var.bronze_dataset_id
  table_id                 = var.cdc_table_id
  schema                   = jsonencode(local.cdc_schema)
  deletion_protection      = var.table_deletion_protection
  require_partition_filter = true
  labels                   = local.labels

  time_partitioning {
    type  = "DAY"
    field = "ingested_at"
  }

  clustering = ["source_table", "operation"]
}

resource "google_bigquery_table_iam_member" "consumer_data_editor" {
  project    = var.project_id
  dataset_id = var.bronze_dataset_id
  table_id   = google_bigquery_table.cdc_events.table_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.consumer.email}"
}

resource "google_project_iam_member" "consumer_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.consumer.email}"
}

resource "google_cloud_run_v2_service" "consumer" {
  name                = var.service_name
  location            = var.region
  project             = var.project_id
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.service_deletion_protection

  labels = local.labels

  lifecycle {
    # O GitHub Actions atualiza somente o digest da imagem.
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }

  template {
    service_account                  = google_service_account.consumer.email
    max_instance_request_concurrency = var.max_instance_request_concurrency

    scaling {
      max_instance_count = var.max_instance_count
    }

    containers {
      image = var.consumer_image

      ports {
        container_port = 8080
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "BQ_CDC_TABLE"
        value = "${var.bronze_dataset_id}.${var.cdc_table_id}"
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

resource "google_cloud_run_v2_service_iam_member" "push_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.consumer.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.push_invoker.email}"
}

resource "google_service_account_iam_member" "pubsub_token_creator" {
  service_account_id = google_service_account.push_invoker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.pubsub_service_agent
}

resource "google_pubsub_subscription" "push" {
  for_each = var.tables

  depends_on = [
    google_bigquery_table_iam_member.consumer_data_editor,
    google_cloud_run_v2_service_iam_member.push_invoker,
    google_service_account_iam_member.pubsub_token_creator,
  ]

  name                       = "${var.push_subscription_prefix}-${each.value}-push-sub"
  project                    = var.project_id
  topic                      = data.google_pubsub_topic.cdc[each.value].id
  ack_deadline_seconds       = 60
  message_retention_duration = var.subscription_message_retention_duration
  retain_acked_messages      = false
  enable_message_ordering    = true
  labels                     = merge(local.labels, { table = each.value, transport = "push" })

  expiration_policy {
    ttl = ""
  }

  retry_policy {
    minimum_backoff = var.minimum_backoff
    maximum_backoff = var.maximum_backoff
  }

  dead_letter_policy {
    dead_letter_topic     = data.google_pubsub_topic.dead_letter.id
    max_delivery_attempts = var.max_delivery_attempts
  }

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.consumer.uri}/pubsub"

    oidc_token {
      service_account_email = google_service_account.push_invoker.email
      audience              = google_cloud_run_v2_service.consumer.uri
    }
  }
}

resource "google_pubsub_subscription_iam_member" "push_service_agent" {
  for_each = var.tables

  project      = var.project_id
  subscription = google_pubsub_subscription.push[each.value].name
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_service_agent
}
