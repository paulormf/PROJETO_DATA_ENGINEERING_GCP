variable "project_id" {
  description = "ID do projeto GCP onde a identidade sera configurada."
  type        = string
}

variable "region" {
  description = "Regiao padrao do provider Google."
  type        = string
  default     = "us-central1"
}

variable "workload_identity_pool_id" {
  description = "ID do pool WIF existente e compartilhado."
  type        = string
  default     = "github-actions"
}

variable "workload_identity_provider_id" {
  description = "ID exclusivo do provider para este repositorio."
  type        = string
  default     = "github-data-engineering-gcp"
}

variable "github_repository" {
  description = "Repositorio GitHub no formato owner/name."
  type        = string
  default     = "paulormf/PROJETO_DATA_ENGINEERING_GCP"

  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repository))
    error_message = "github_repository deve estar no formato owner/name."
  }
}

variable "deployer_service_account_id" {
  description = "ID da service account dedicada ao deploy das DAGs."
  type        = string
  default     = "de-github-composer-deployer"
}

variable "composer_dags_bucket" {
  description = "Bucket do Composer que contem a pasta dags/."
  type        = string
}
