variable "project_id" {
  description = "ID do projeto GCP onde os recursos serao provisionados."
  type        = string
}

variable "region" {
  description = "Regiao do bucket e dos servicos analiticos."
  type        = string
  default     = "us-central1"
}

variable "bucket_name" {
  description = "Nome globalmente unico do bucket Bronze."
  type        = string
}

variable "bucket_labels" {
  description = "Labels aplicadas ao bucket."
  type        = map(string)
  default = {
    environment = "lab"
    layer       = "bronze"
    managed_by  = "terraform"
  }
}

variable "lifecycle_delete_age_days" {
  description = "Se informado, remove objetos com essa idade. Nulo desativa a regra."
  type        = number
  default     = null
  nullable    = true

  validation {
    condition     = var.lifecycle_delete_age_days == null || var.lifecycle_delete_age_days > 0
    error_message = "lifecycle_delete_age_days deve ser nulo ou maior que zero."
  }
}

variable "ingestion_service_account_id" {
  description = "ID da service account dedicada a gravar objetos Bronze."
  type        = string
  default     = "de-ingestion-writer"
}
