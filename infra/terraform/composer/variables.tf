variable "project_id" {
  description = "ID do projeto GCP."
  type        = string
}

variable "region" {
  description = "Regiao do ambiente Composer e do Cloud Run Job."
  type        = string
  default     = "us-central1"
}

variable "environment_name" {
  description = "Nome do ambiente Managed Service for Apache Airflow."
  type        = string
  default     = "ecommerce-composer-lab"
}

variable "composer_service_account_id" {
  description = "ID da service account usada pelo ambiente Composer."
  type        = string
  default     = "de-composer-orchestrator"
}

variable "image_version" {
  description = "Versao exata da imagem Composer 3 escolhida no Console."
  type        = string

  validation {
    condition     = can(regex("^composer-3-", var.image_version))
    error_message = "image_version deve ser uma imagem Composer 3."
  }
}

variable "materializer_job_name" {
  description = "Cloud Run Job que a DAG executara com overrides."
  type        = string
  default     = "ecommerce-bronze-materializer"
}

variable "labels" {
  description = "Labels aplicadas ao ambiente Composer."
  type        = map(string)
  default = {
    environment = "lab"
    component   = "orchestration"
    managed_by  = "terraform"
  }
}
