variable "project_id" {
  description = "Projeto GCP do Cloud Run Job."
  type        = string
}

variable "region" {
  description = "Regiao do Cloud Run Job."
  type        = string
  default     = "us-central1"
}

variable "bucket_name" {
  description = "Bucket Bronze que recebera o envelope Raw da API."
  type        = string
}

variable "service_account_id" {
  description = "ID da service account dedicada ao extrator API."
  type        = string
  default     = "de-api-extract-writer"
}

variable "job_name" {
  description = "Nome do Cloud Run Job do extrator API."
  type        = string
  default     = "ecommerce-api-extract"
}

variable "api_extract_image" {
  description = "Imagem do extrator publicada por digest imutavel."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.api_extract_image))
    error_message = "api_extract_image deve referenciar uma imagem por digest sha256."
  }
}

variable "job_default_args" {
  description = "Argumentos fallback do job; o orquestrador deve gerar o object_name por execucao."
  type        = list(string)

  validation {
    condition     = length(var.job_default_args) >= 4
    error_message = "job_default_args deve informar projeto, bucket e object_name."
  }
}

variable "max_retries" {
  description = "Quantidade de retries do Cloud Run Job."
  type        = number
  default     = 1

  validation {
    condition     = var.max_retries >= 0 && var.max_retries <= 10
    error_message = "max_retries deve estar entre 0 e 10."
  }
}

variable "task_timeout" {
  description = "Timeout maximo da execucao."
  type        = string
  default     = "900s"
}

variable "cpu_limit" {
  description = "Limite de CPU do container."
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Limite de memoria do container."
  type        = string
  default     = "512Mi"
}
