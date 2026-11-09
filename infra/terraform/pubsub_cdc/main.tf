data "google_project" "current" {
  project_id = var.project_id
}

locals {
  labels = {
    environment = "lab"
    layer       = "bronze"
    managed_by  = "terraform"
    pipeline    = "cdc"
  }
  pubsub_service_agent = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic" "cdc" {
  for_each = var.tables

  deletion_policy            = var.deletion_policy
  name                       = "${var.topic_prefix}.${var.source_schema}.${each.value}"
  message_retention_duration = var.topic_message_retention_duration
  labels                     = merge(local.labels, { table = each.value })
}

resource "google_pubsub_topic" "dead_letter" {
  deletion_policy = var.deletion_policy
  name            = "${var.topic_prefix}.dead-letter"
  labels          = merge(local.labels, { purpose = "dead-letter" })
}

resource "google_pubsub_topic" "heartbeat" {
  deletion_policy            = var.deletion_policy
  name                       = "${var.topic_prefix}.heartbeat"
  message_retention_duration = var.topic_message_retention_duration
  labels                     = merge(local.labels, { purpose = "heartbeat" })
}

resource "google_service_account" "debezium_publisher" {
  account_id   = var.debezium_service_account_id
  display_name = "CDC Debezium publisher"
  project      = var.project_id
}

resource "google_pubsub_subscription" "cdc" {
  for_each = var.tables

  deletion_policy            = var.deletion_policy
  name                       = "${var.subscription_prefix}-${each.value}-sub"
  topic                      = google_pubsub_topic.cdc[each.value].id
  ack_deadline_seconds       = 60
  message_retention_duration = var.subscription_message_retention_duration
  retain_acked_messages      = false
  enable_message_ordering    = true
  labels                     = merge(local.labels, { table = each.value })

  expiration_policy {
    ttl = ""
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 20
  }
}

resource "google_pubsub_subscription" "dead_letter" {
  deletion_policy            = var.deletion_policy
  name                       = "${var.subscription_prefix}-dead-letter-sub"
  topic                      = google_pubsub_topic.dead_letter.id
  ack_deadline_seconds       = 60
  message_retention_duration = var.dead_letter_message_retention_duration
  retain_acked_messages      = true
  labels                     = merge(local.labels, { purpose = "dead-letter" })

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_subscription" "heartbeat" {
  deletion_policy            = var.deletion_policy
  name                       = "${var.subscription_prefix}-heartbeat-sub"
  topic                      = google_pubsub_topic.heartbeat.id
  ack_deadline_seconds       = 60
  message_retention_duration = var.subscription_message_retention_duration
  retain_acked_messages      = false
  labels                     = merge(local.labels, { purpose = "heartbeat" })

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_topic_iam_member" "dead_letter_publisher" {
  topic  = google_pubsub_topic.dead_letter.name
  role   = "roles/pubsub.publisher"
  member = local.pubsub_service_agent
}

resource "google_pubsub_topic_iam_member" "heartbeat_publisher" {
  topic  = google_pubsub_topic.heartbeat.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.debezium_publisher.email}"
}

resource "google_pubsub_topic_iam_member" "debezium_publisher" {
  for_each = var.tables

  topic  = google_pubsub_topic.cdc[each.value].name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.debezium_publisher.email}"
}

resource "google_pubsub_subscription_iam_member" "cdc_service_agent" {
  for_each = var.tables

  subscription = google_pubsub_subscription.cdc[each.value].name
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_service_agent
}
