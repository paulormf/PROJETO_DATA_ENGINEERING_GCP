variable "project_id" {
  description = "Projeto GCP que hospeda o Dataform e os datasets BigQuery."
  type        = string
}

variable "region" {
  description = "Regiao padrao do provider para recursos GCP."
  type        = string
  default     = "us-central1"
}

variable "dataform_region" {
  description = "Regiao do repositorio Dataform."
  type        = string
  default     = "us-central1"
}

variable "bigquery_location" {
  description = "Localizacao dos datasets BigQuery de saida do Dataform."
  type        = string
  default     = "us-central1"
}

variable "bronze_dataset_id" {
  description = "Dataset Bronze existente, lido pelo Dataform."
  type        = string
  default     = "ecommerce_bronze"
}

variable "silver_dataset_id" {
  description = "Dataset BigQuery que recebera os modelos Silver."
  type        = string
  default     = "ecommerce_silver"
}

variable "assertion_dataset_id" {
  description = "Dataset BigQuery que recebera as assertions do Dataform."
  type        = string
  default     = "ecommerce_dataform_assertions"
}

variable "dataform_repository_id" {
  description = "ID do repositorio Dataform."
  type        = string
  default     = "ecommerce-dataform"
}

variable "dataform_repository_display_name" {
  description = "Nome amigavel do repositorio Dataform."
  type        = string
  default     = "Ecommerce Dataform"
}

variable "dataform_service_account_id" {
  description = "Service account usada pelas execucoes do Dataform."
  type        = string
  default     = "de-dataform-runner"
}
