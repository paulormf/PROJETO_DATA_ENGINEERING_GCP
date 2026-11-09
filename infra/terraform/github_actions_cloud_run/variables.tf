variable "project_id" {
  description = "ID do projeto GCP onde a identidade sera criada."
  type        = string
}

variable "region" {
  description = "Regiao padrao dos recursos Cloud Run."
  type        = string
  default     = "us-central1"
}

variable "workload_identity_pool_id" {
  description = "ID do pool WIF existente e compartilhado."
  type        = string
  default     = "github-actions"
}

variable "workload_identity_provider_id" {
  description = "ID do provider WIF ja criado para este repositorio."
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
  description = "ID da service account dedicada ao build/deploy dos Jobs Cloud Run."
  type        = string
  default     = "de-github-cloud-run-deployer"
}

variable "artifact_registry_location" {
  description = "Localizacao do repositorio Artifact Registry."
  type        = string
  default     = "us-central1"
}

variable "artifact_registry_repository" {
  description = "ID do repositorio Artifact Registry existente."
  type        = string
  default     = "data-engineering"
}

variable "runtime_service_account_ids" {
  description = "IDs das service accounts que os Jobs usam em runtime."
  type        = set(string)
  default = [
    "de-ingestion-writer",
    "de-bronze-materializer",
  ]
}
