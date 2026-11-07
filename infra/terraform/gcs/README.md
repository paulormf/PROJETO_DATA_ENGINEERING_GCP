# Cloud Storage Bronze — Terraform

Este modulo descreve, mas ainda nao aplica, a fundacao da camada Bronze no Cloud Storage.

## Recursos declarados

- bucket regional Standard em `us-central1` por padrao;
- acesso uniforme no nivel do bucket;
- prevencao de acesso publico;
- `force_destroy = false`, evitando exclusao acidental de objetos;
- lifecycle de exclusao opcional, desativado por padrao;
- service account dedicada;
- permissao `roles/storage.objectUser` somente no bucket Bronze.

O writer pode criar, ler, atualizar e excluir objetos no bucket Bronze. Esse escopo e necessario para atualizar checkpoints e recuperar partes de uma execucao. Ele nao recebe permissao para administrar o bucket ou outros recursos do projeto.

## Pre-requisitos

- Terraform instalado;
- provider Google disponivel;
- faturamento e APIs necessarias habilitados no projeto;
- identidade local autenticada para executar Terraform;
- nome de bucket globalmente unico escolhido.

## Fluxo seguro

1. Copiar `terraform.tfvars.example` para `terraform.tfvars`.
2. Substituir o nome do bucket por um valor globalmente unico.
3. Executar `terraform fmt`.
4. Executar `terraform init`.
5. Executar `terraform validate`.
6. Executar `terraform plan` e revisar os recursos.
7. Somente apos aprovacao explicita executar `terraform apply`.

O arquivo `terraform.tfvars` nao deve ser versionado se contiver valores especificos do ambiente. Nenhuma chave privada de service account deve ser criada.

## Decisoes pendentes

- nome final do bucket;
- politica de retencao/lifecycle;
- necessidade de leitor separado para BigQuery ou jobs;
- estrategia de dev, homologacao e producao;
- se a service account sera criada por este modulo ou por uma fundacao IAM central.
