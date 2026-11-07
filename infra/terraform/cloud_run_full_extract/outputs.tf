output "secret_ids" {
  description = "IDs dos secrets criados, sem expor valores."
  value       = { for key, secret in google_secret_manager_secret.postgres : key => secret.secret_id }
}

output "runtime_service_account_email" {
  description = "Service account que podera acessar os secrets."
  value       = var.ingestion_service_account_email
}
