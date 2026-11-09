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
