# Catalogo de ingestao

Catalogo tecnico confirmado a partir dos metadados do PostgreSQL `appdb`, schema `ecommerce`.

## Estrategia geral

- Carga inicial: full batch de todas as tabelas, executada pelo Cloud Run Job.
- Mudancas posteriores: Debezium CDC para insert, update e delete.
- Watermark: usado como estrategia complementar de reconciliacao ou backfill nas tabelas com coluna de atualizacao confiavel; nao substitui o CDC nesta arquitetura.
- Bronze: preservacao tecnica dos eventos/lotes.
- Silver: deduplicacao, qualidade, integridade referencial e regras de negocio.

## Tabelas

| Tabela | Linhas observadas | PK confirmada | Watermark candidato | Tratamento inicial |
|---|---:|---|---|---|
| `armazens` | 5 | `armazem_id` | `criado_em` | full + CDC |
| `categorias` | 100 | `categoria_id` | `criado_em` | full + CDC |
| `clientes` | 200000 | `cliente_id` | `atualizado_em` | full + CDC |
| `enderecos_clientes` | 200000 | `endereco_id` | `criado_em` | full + CDC |
| `envios` | 1000000 | `envio_id` | nenhum confiavel confirmado | full + CDC |
| `estoque` | 500000 | (`armazem_id`, `variante_id`) | `atualizado_em` | full + CDC |
| `eventos_clientes` | 10000000 | `evento_id` | `ocorrido_em` e tempo do evento, nao watermark de update | full + CDC |
| `itens_pedido` | 2999995 | `item_pedido_id` | nenhum | full + CDC |
| `marcas` | 500 | `marca_id` | `criado_em` | full + CDC |
| `pagamentos` | 1000000 | `pagamento_id` | nenhum confiavel confirmado | full + CDC |
| `pedidos` | 999559 | `pedido_id` | `atualizado_em` | full + CDC |
| `produtos` | 100000 | `produto_id` | `atualizado_em` | full + CDC |
| `variantes_produtos` | 100000 | `variante_id` | `atualizado_em` | full + CDC |

As contagens sao as observadas na descoberta e podem mudar enquanto o PostgreSQL continua recebendo operacoes.

## Dependencias confirmadas

- `categorias.categoria_pai_id` -> `categorias.categoria_id`
- `enderecos_clientes.cliente_id` -> `clientes.cliente_id`
- `envios.armazem_id` -> `armazens.armazem_id`
- `envios.pedido_id` -> `pedidos.pedido_id`
- `estoque.armazem_id` -> `armazens.armazem_id`
- `estoque.variante_id` -> `variantes_produtos.variante_id`
- `eventos_clientes.cliente_id` -> `clientes.cliente_id`
- `eventos_clientes.pedido_id` -> `pedidos.pedido_id`
- `eventos_clientes.produto_id` -> `produtos.produto_id`
- `itens_pedido.pedido_id` -> `pedidos.pedido_id`
- `itens_pedido.variante_id` -> `variantes_produtos.variante_id`
- `pagamentos.pedido_id` -> `pedidos.pedido_id`
- `pedidos.cliente_id` -> `clientes.cliente_id`
- `pedidos.endereco_cobranca_id` -> `enderecos_clientes.endereco_id`
- `pedidos.endereco_entrega_id` -> `enderecos_clientes.endereco_id`
- `produtos.categoria_id` -> `categorias.categoria_id`
- `produtos.marca_id` -> `marcas.marca_id`
- `variantes_produtos.produto_id` -> `produtos.produto_id`

## Indices unicos relevantes

- `clientes.email`
- `envios.codigo_rastreamento` — coluna nullable; a regra de unicidade precisa considerar o comportamento de nulos do PostgreSQL.
- `marcas.nome_marca`
- `pagamentos.referencia_transacao`
- `variantes_produtos.sku`

## Observacoes para o pipeline

1. Nao existe `deleted_at` confirmado nas tabelas. Como os deletes sao fisicos, o CDC deve permanecer ativo para capturar operacoes `d`.
2. `criado_em` identifica inclusao, mas nao captura atualizacoes posteriores. Nao deve ser usado sozinho como watermark de uma tabela mutavel.
3. `atualizado_em` e candidato tecnico para clientes, estoque, pedidos, produtos e variantes, mas deve ser combinado com uma estrategia para empates e deletes.
4. `ocorrido_em` em `eventos_clientes` representa o momento do evento de negocio, nao necessariamente a ordem de commit no PostgreSQL.
5. A carga Bronze nao deve depender da ordem das FKs. A ordem de dependencias sera importante na Silver e nos data marts.

## Ordem logica para transformacoes posteriores

1. `armazens`, `categorias`, `marcas`, `clientes`;
2. `enderecos_clientes`, `produtos`;
3. `variantes_produtos`, `estoque`;
4. `pedidos`;
5. `itens_pedido`, `pagamentos`, `envios`;
6. `eventos_clientes`.

Essa ordem e para dependencias analiticas. A orquestracao da carga Bronze podera executar tabelas independentes em paralelo, respeitando limites de conexao e impacto no PostgreSQL.
