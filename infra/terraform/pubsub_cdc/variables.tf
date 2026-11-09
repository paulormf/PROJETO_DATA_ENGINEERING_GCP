variable "project_id" {
  description = "Projeto GCP dos topicos e assinaturas CDC."
  type        = string
}

variable "region" {
  description = "Regiao usada pelo endpoint locacional do Pub/Sub."
  type        = string
  default     = "us-central1"
}

variable "topic_prefix" {
  description = "Prefixo fisico dos topicos Debezium."
  type        = string
  default     = "ecommerce_gcp_v2"
}

variable "subscription_prefix" {
  description = "Prefixo dos nomes das assinaturas CDC."
  type        = string
  default     = "ecommerce-gcp-v2"
}

variable "debezium_service_account_id" {
  description = "ID da service account que o runtime Debezium usara para publicar eventos."
  type        = string
  default     = "de-cdc-publisher"
}

variable "deletion_policy" {
  description = "Politica ao destruir recursos gerenciados pelo Terraform."
  type        = string
  default     = "ABANDON"

  validation {
    condition     = contains(["ABANDON", "DELETE"], var.deletion_policy)
    error_message = "deletion_policy deve ser ABANDON ou DELETE."
  }
}

variable "source_schema" {
  description = "Schema de origem usado no nome dos topicos Debezium."
  type        = string
  default     = "ecommerce"
}

variable "tables" {
  description = "Tabelas cobertas pelo ciclo CDC v2."
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

variable "topic_message_retention_duration" {
  description = "Retencao no topico para permitir replay do ciclo CDC."
  type        = string
  default     = "604800s"
}

variable "subscription_message_retention_duration" {
  description = "Retencao do backlog nao confirmado da assinatura."
  type        = string
  default     = "604800s"
}

variable "dead_letter_message_retention_duration" {
  description = "Retencao da assinatura de quarentena."
  type        = string
  default     = "2678400s"
}
