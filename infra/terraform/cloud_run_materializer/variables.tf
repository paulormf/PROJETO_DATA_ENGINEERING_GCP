variable "project_id" {
  description = "ID do projeto GCP onde a identidade sera criada."
  type        = string
}

variable "region" {
  description = "Regiao documentada para o workload."
  type        = string
  default     = "us-central1"
}

variable "bucket_name" {
  description = "Nome do bucket Bronze que contem os manifests e Parquets."
  type        = string
}

variable "bronze_dataset_id" {
  description = "Dataset BigQuery Bronze ja existente ou criado pela fundacao."
  type        = string
  default     = "ecommerce_bronze"
}

variable "materializer_service_account_id" {
  description = "ID da service account dedicada ao materializer."
  type        = string
  default     = "de-bronze-materializer"
}

variable "job_name" {
  description = "Nome do Cloud Run Job de materializacao."
  type        = string
  default     = "ecommerce-bronze-materializer"
}

variable "materializer_image" {
  description = "Imagem do materializer publicada por digest imutavel."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.materializer_image))
    error_message = "materializer_image deve referenciar uma imagem por digest sha256."
  }
}

variable "job_default_args" {
  description = "Argumentos fallback; o Composer devera sobrescreve-los nas execucoes."
  type        = list(string)

  validation {
    condition     = length(var.job_default_args) > 0
    error_message = "job_default_args deve conter uma configuracao valida de fallback."
  }
}

variable "max_retries" {
  description = "Quantidade de retries do task Cloud Run."
  type        = number
  default     = 1

  validation {
    condition     = var.max_retries >= 0 && var.max_retries <= 10
    error_message = "max_retries deve estar entre 0 e 10."
  }
}

variable "task_timeout" {
  description = "Timeout maximo do task Cloud Run."
  type        = string
  default     = "3600s"
}

variable "cpu_limit" {
  description = "Limite de CPU do task."
  type        = string
  default     = "2"
}

variable "memory_limit" {
  description = "Limite de memoria do task."
  type        = string
  default     = "4Gi"
}
