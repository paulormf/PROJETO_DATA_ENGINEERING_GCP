output "cdc_topic_names" {
  description = "Topicos Debezium criados para o ciclo CDC v2."
  value       = { for table, topic in google_pubsub_topic.cdc : table => topic.name }
}

output "cdc_subscription_names" {
  description = "Assinaturas Pull do ciclo CDC v2."
  value       = { for table, subscription in google_pubsub_subscription.cdc : table => subscription.name }
}

output "dead_letter_topic_name" {
  description = "Topico compartilhado de quarentena."
  value       = google_pubsub_topic.dead_letter.name
}

output "dead_letter_subscription_name" {
  description = "Assinatura de quarentena."
  value       = google_pubsub_subscription.dead_letter.name
}

output "debezium_publisher_service_account_email" {
  description = "Service account que deve ser associada ao runtime do Debezium."
  value       = google_service_account.debezium_publisher.email
}
