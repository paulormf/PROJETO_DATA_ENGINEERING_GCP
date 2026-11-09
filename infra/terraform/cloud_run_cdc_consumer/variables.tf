variable "project_id" {
  description = "Projeto GCP do consumidor CDC."
  type        = string
}

variable "region" {
  description = "Regiao do servico Cloud Run."
  type        = string
  default     = "us-central1"
}

variable "bronze_dataset_id" {
  description = "Dataset BigQuery Bronze que recebera os eventos CDC."
  type        = string
  default     = "ecommerce_bronze"
}

variable "cdc_table_id" {
  description = "Tabela central append-only para os eventos CDC."
  type        = string
  default     = "cdc_events_raw"
}

variable "source_schema" {
  description = "Schema PostgreSQL usado no nome dos topicos Debezium."
  type        = string
  default     = "ecommerce"
}

variable "topic_prefix" {
  description = "Prefixo dos topicos CDC ja administrados pelo modulo Pub/Sub."
  type        = string
  default     = "ecommerce_gcp_v2"
}

variable "tables" {
  description = "Tabelas cobertas pelas assinaturas push CDC."
  type        = set(string)
  default = [
    "armazens",
    "categorias",
    "clientes",
    "enderecos_clientes",
    "envios",
    "estoque",
    "eventos_clientes",
    "itens_pedido",
    "marcas",
    "pagamentos",
    "pedidos",
    "produtos",
    "variantes_produtos",
  ]
}

variable "consumer_service_account_id" {
  description = "Service account usada pelo Cloud Run para gravar no BigQuery."
  type        = string
  default     = "de-cdc-consumer"
}

variable "push_invoker_service_account_id" {
  description = "Service account usada pelo Pub/Sub para autenticar o push."
  type        = string
  default     = "de-cdc-push-invoker"
}

variable "service_name" {
  description = "Nome do servico Cloud Run que recebe os eventos CDC."
  type        = string
  default     = "ecommerce-cdc-consumer"
}

variable "consumer_image" {
  description = "Imagem do consumidor publicada no Artifact Registry por digest imutavel."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.consumer_image))
    error_message = "consumer_image deve referenciar uma imagem por digest sha256."
  }
}

variable "push_subscription_prefix" {
  description = "Prefixo dos nomes das assinaturas push."
  type        = string
  default     = "ecommerce-gcp-v2"
}

variable "subscription_message_retention_duration" {
  description = "Retencao do backlog nao confirmado das assinaturas push."
  type        = string
  default     = "604800s"
}

variable "dead_letter_message_retention_duration" {
  description = "Retencao da assinatura de quarentena."
  type        = string
  default     = "2678400s"
}

variable "max_delivery_attempts" {
  description = "Tentativas antes do encaminhamento para a DLQ."
  type        = number
  default     = 20

  validation {
    condition     = var.max_delivery_attempts >= 5 && var.max_delivery_attempts <= 100
    error_message = "max_delivery_attempts deve estar entre 5 e 100."
  }
}

variable "minimum_backoff" {
  description = "Backoff minimo das entregas Pub/Sub."
  type        = string
  default     = "10s"
}

variable "maximum_backoff" {
  description = "Backoff maximo das entregas Pub/Sub."
  type        = string
  default     = "600s"
}

variable "max_instance_count" {
  description = "Limite de instancias do consumidor Cloud Run."
  type        = number
  default     = 10
}

variable "max_instance_request_concurrency" {
  description = "Quantidade maxima de requisicoes simultaneas por instancia."
  type        = number
  default     = 20
}

variable "cpu_limit" {
  description = "Limite de CPU por instancia."
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Limite de memoria por instancia."
  type        = string
  default     = "512Mi"
}

variable "table_deletion_protection" {
  description = "Protecao contra exclusao da tabela raw CDC."
  type        = bool
  default     = false
}

variable "service_deletion_protection" {
  description = "Protecao contra exclusao do servico Cloud Run."
  type        = bool
  default     = false
}
