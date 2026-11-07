variable "project_id" {
  description = "ID do projeto GCP."
  type        = string
}

variable "region" {
  description = "Regiao usada pelo job Cloud Run."
  type        = string
  default     = "us-central1"
}

variable "ingestion_service_account_email" {
  description = "Service account ja criada para gravar objetos Bronze."
  type        = string
}

variable "secret_ids" {
  description = "IDs dos secrets de conexao PostgreSQL."
  type        = map(string)
  default = {
    postgres_host     = "ecommerce-postgres-host"
    postgres_user     = "ecommerce-postgres-user"
    postgres_password = "ecommerce-postgres-password"
  }
}
