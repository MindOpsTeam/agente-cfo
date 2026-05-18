# Bling API v3 — Mapa completo de endpoints (MCP virtualization spec)

**Base URL (chamadas autenticadas):** `https://api.bling.com.br/Api/v3` — ⚠️ tokens JWT NÃO funcionam em `www.bling.com.br/Api/v3` (retorna 403 FORBIDDEN). A doc oficial às vezes cita o host `www`, mas só o host `api` aceita Bearer JWT.
**Base URL (OAuth authorize/token):** `https://www.bling.com.br/Api/v3` — o fluxo OAuth (`/oauth/authorize`, `/oauth/token`) usa o host `www`; só as chamadas com Bearer token usam `api`.
**Auth:** OAuth 2.0 (`Authorization: Bearer <access_token>`)
**Fonte:** SDK `AlexandreBellas/bling-erp-api-js` (sync com API v310 — 2024-10-02), validado contra doc oficial em `developer.bling.com.br/referencia`.
**Rate limit oficial:** 3 req/s por aplicativo (HTTP 429 quando excede) → MCP precisa de token bucket + retry exponencial.

---

## 1. Inventário (43 entidades)

| # | Entidade | Path raiz | Métodos SDK |
|---|---|---|---|
| 1 | Borderôs | `/borderos` | delete, find |
| 2 | Campos Customizados | `/campos-customizados` | delete, getModules, getTypes, findModule, find, changeSituation, create, update |
| 3 | Canais de Venda | `/canais-venda` | get, find, getTypes |
| 4 | Categorias - Lojas | `/categorias/lojas` | CRUD completo |
| 5 | **Categorias - Produtos** | `/categorias/produtos` | CRUD completo |
| 6 | Categorias - Receitas/Despesas | `/categorias/receitas-despesas` | get, find |
| 7 | Contas Contábeis | `/contas-contabeis` | get, find |
| 8 | Contas a Pagar | `/contas/pagar` | CRUD + baixar |
| 9 | Contas a Receber | `/contas/receber` | CRUD + boletos + baixar + cancelar |
| 10 | Contatos | `/contatos` | CRUD + deleteMany + changeSituation(Many) + consumidor-final + tipos |
| 11 | Contatos - Tipos | `/contatos/tipos` | get |
| 12 | Contratos | `/contratos` | CRUD |
| 13 | **Depósitos** | `/depositos` | get, find, create, update |
| 14 | Empresas | `/empresas/me/dados-basicos` | me |
| 15 | **Estoques** | `/estoques` | findBalance, getBalances, create, update |
| 16 | Formas de Pagamento | `/formas-pagamentos` | CRUD |
| 17 | **Grupos de Produtos** | `/grupos-produtos` | CRUD + deleteMany |
| 18 | Homologação | `/homologacao/produtos` | CRUD + execute |
| 19 | Logísticas | `/logisticas` | CRUD |
| 20 | Logísticas - Etiquetas | `/logisticas/etiquetas` | get |
| 21 | Logísticas - Objetos | `/logisticas/objetos` | CRUD |
| 22 | Logísticas - Remessas | `/logisticas/remessas` | CRUD + getByLogistic |
| 23 | Logísticas - Serviços | `/logisticas/servicos` | CRUD + changeSituation |
| 24 | Naturezas de Operações | `/naturezas-operacoes` | get, obtainTax |
| 25 | NFC-e | `/nfce` | CRUD + enviar + lançar/estornar contas/estoque |
| 26 | NF-e | `/nfe` | CRUD + enviar + lançar/estornar contas/estoque |
| 27 | NFS-e | `/nfse` | CRUD + enviar + cancelar + configuracoes |
| 28 | Notificações | `/notificacoes` | get, read |
| 29 | Ordens de Produção | `/ordens-producao` | CRUD + gerar-sob-demanda + changeSituation |
| 30 | Pedidos - Compras | `/pedidos/compras` | CRUD + changeSituation + lançar/estornar contas/estoque |
| 31 | Pedidos - Vendas | `/pedidos/vendas` | CRUD + deleteMany + changeSituation + lançar/estornar + gerar NFe/NFCe |
| 32 | **Produtos** | `/produtos` | CRUD + deleteMany + changeSituation(Many) |
| 33 | Produtos - Estruturas | `/produtos/estruturas` | gerencia BOM (componentes) |
| 34 | **Produtos - Fornecedores** | `/produtos/fornecedores` | CRUD |
| 35 | **Produtos - Lojas** | `/produtos/lojas` | CRUD |
| 36 | Produtos - Variações | `/produtos/variacoes` | find, changeAttributeName, generateCombinations |
| 37 | Propostas Comerciais | `/propostas-comerciais` | CRUD + deleteMany + changeSituation |
| 38 | Situações | `/situacoes` | CRUD |
| 39 | Situações - Módulos | `/situacoes/modulos` | getModules + acoes + transicoes |
| 40 | Situações - Transições | `/situacoes/transicoes` | CRUD |
| 41 | Usuários | `/usuarios` | validateHash, changePassword, recoverPassword |
| 42 | Vendedores | `/vendedores` | get, find |
| 43 | Campos Customizados (módulos/tipos) | sub-rotas de `/campos-customizados` | já contabilizado em #2 |

**Negrito = entidades obrigatórias pro workflow "upload XLS → cadastro de produtos".**

---

## 2. Endpoints completos por entidade

### Produtos (CRÍTICO)
- `GET    /produtos` — lista; query params: `pagina`, `limite`, `criterio`, `tipo`, `idComponente`, `dataInclusaoInicial`, `dataInclusaoFinal`, `dataAlteracaoInicial`, `dataAlteracaoFinal`, `idCategoria`, `idLoja`, `codigo`, `nome`, `idsProdutos[]`, `codigos[]`
- `GET    /produtos/{idProduto}`
- `POST   /produtos` — cria (1 produto por chamada)
- `PUT    /produtos/{idProduto}` — replace completo
- `PATCH  /produtos/{idProduto}/situacoes` — só altera `situacao`
- `POST   /produtos/situacoes` — altera situação em lote
- `DELETE /produtos/{idProduto}`
- `DELETE /produtos?idsProdutos=` — em lote

### Produtos - Estruturas (BOM)
- `GET    /produtos/estruturas/{idProdutoEstrutura}`
- `POST   /produtos/estruturas/{idProdutoEstrutura}/componentes`
- `PATCH  /produtos/estruturas/{idProdutoEstrutura}/componentes/{idComponente}`
- `DELETE /produtos/estruturas/{idProdutoEstrutura}/componentes`
- `DELETE /produtos/estruturas`
- `PUT    /produtos/estruturas/{idProdutoEstrutura}`

### Produtos - Fornecedores
- `GET/POST/PUT/DELETE /produtos/fornecedores[/{id}]`
- POST exige: `produto.id`, `fornecedor.id` (contato tipo F)
- Opcionais: `descricao`, `codigo`, `precoCusto`, `precoCompra`, `padrao`, `garantia`

### Produtos - Lojas (anúncios em marketplaces)
- `GET/POST/PUT/DELETE /produtos/lojas[/{id}]`
- POST exige: `codigo`, `produto.id`, `loja.id`
- Opcionais: `preco`, `precoPromocional`, `fornecedorLoja.id`, `marcaLoja.id`, `categoriasProdutos[].id`

### Produtos - Variações
- `GET    /produtos/variacoes/{idProdutoPai}`
- `PATCH  /produtos/variacoes/{idProdutoPai}/atributos`
- `POST   /produtos/variacoes/atributos/gerar-combinacoes`

### Categorias - Produtos
- `GET/POST/PUT/DELETE /categorias/produtos[/{id}]`
- POST: `descricao` (obrig.), `categoriaPai.id` (opcional)
- ⚠️ Sem criação em árvore numa chamada — precisa encadear

### Depósitos
- `GET/POST/PUT /depositos[/{id}]`
- POST: `descricao`, `situacao` ("A"|"I"), `padrao`, `desconsiderarSaldo`

### Estoques
- `GET  /estoques/saldos` — saldo consolidado
- `GET  /estoques/saldos/{idDeposito}` — saldo de um depósito
- `POST /estoques` — lança movimentação
- `PUT  /estoques/{idEstoque}`

### Grupos de Produtos
- `GET/POST/PUT/DELETE /grupos-produtos[/{id}]`
- POST: `nome`, `grupoProdutoPai.id` (⚠️ obrigatório — não dá pra criar grupo raiz via API)

### Outros relevantes pro fluxo
- `GET /canais-venda` — pra preencher `loja.id` em `/produtos/lojas`
- `GET /contatos` — fornecedor é Contato com tipo "F"
- `GET /campos-customizados/modulos/{idModulo}` — pra mapear campos custom do módulo Produtos

*(Os outros 30+ recursos seguem o mesmo padrão REST — ver inventário acima para sumário.)*

---

## 3. Schema completo `POST /produtos`

### Root (obrigatórios)
| Campo | Tipo | Notas |
|---|---|---|
| `nome` | string | |
| `tipo` | enum | `"S"` Serviço \| `"P"` Produto \| `"N"` Serviço 06 21 22 |
| `situacao` | enum | `"A"` Ativo \| `"I"` Inativo |
| `formato` | enum | `"S"` Simples \| `"V"` Com variações \| `"E"` Com composição |
| `variacoes` | array | mande `[]` se `formato="S"` |

### Root (opcionais)
`id`, `codigo` (SKU), `preco`, `descricaoCurta`, `dataValidade`, `unidade` (string livre: "UN", "PC", "KG"...), `pesoLiquido`, `pesoBruto`, `volumes`, `itensPorCaixa`, `gtin` (validado!), `gtinEmbalagem`, `tipoProducao` (`"P"`|`"T"`), `condicao` (0/1/2), `freteGratis` (bool), `marca` (string livre — sem entidade `/marcas`!), `descricaoComplementar`, `linkExterno`, `observacoes`, `categoria.id`, `linhaProduto.id`, `actionEstoque` (`"Z"`|`"T"`)

### `estoque` (objeto opcional)
`minimo`, `maximo`, `crossdocking` (dias), `localizacao`

### `dimensoes`
`largura`, `altura`, `profundidade`, `unidadeMedida` (number — código interno)

### `tributacao`
`origem` (0-8), `nFCI`, `ncm` (validado!), `cest`, `codigoListaServicos`, `spedTipoItem`, `codigoItem`, `percentualTributos`, `valorBaseStRetencao`, `valorStRetencao`, `valorICMSSubstituto`, `codigoExcecaoTipi`, `classeEnquadramentoIpi`, `valorIpiFixo`, `codigoSeloIpi`, `valorPisFixo`, `valorCofinsFixo`, `codigoANP`, `descricaoANP`, `percentualGLP`, `percentualGasNacional`, `percentualGasImportado`, `valorPartida`, `tipoArmamento` (0|1), `descricaoCompletaArmamento`, `dadosAdicionais`, `grupoProduto.id`

### `midia`
`video.url`, `imagens.externas[].link` (URLs públicas — Bling baixa; falhas viram `warnings[]`)

### `estrutura` (quando `formato="E"`)
`tipoEstoque` (`"F"`|`"V"`), `lancamentoEstoque` (`"A"`|`"M"`|`"P"`), `componentes[].produto.id`, `componentes[].quantidade`

### `variacoes` (quando `formato="V"`)
Array de objetos com TODOS os campos do produto raiz + `variacao: { nome, ordem, produtoPai.cloneInfo }`

### `camposCustomizados`
`[{ idCampoCustomizado, idVinculo?, valor?, item? }]`

### Response
```json
{ "data": { "id": 123, "warnings": ["..."] } }
```

---

## 4. Dependências para construir um cadastro completo via XLS

| Pra preencher... | Cria/consulta antes em... | Notas |
|---|---|---|
| `categoria.id` | `GET/POST /categorias/produtos` | Encadear hierarquia |
| `tributacao.grupoProduto.id` | `GET/POST /grupos-produtos` | Precisa de pai existente |
| Movimentação por depósito | `GET /depositos` + `POST /estoques` | Crie depósito padrão antes |
| `fornecedor.id` | `GET/POST /contatos` (tipo "F") | Fornecedor = Contato |
| `loja.id` em anúncios | `GET /canais-venda` | Canal precisa estar conectado no painel |
| **Marca** | ❌ não há endpoint `/marcas` | É string livre no produto |
| **Unidades de medida** | ❌ não há endpoint | `unidade` é string livre |
| Campos customizados | `GET /campos-customizados/modulos/{id}` | Módulo Produtos |
| Linha de produto | ❌ sem endpoint público | Provavelmente legado |

---

## 5. Pegadinhas operacionais (XLS workflow)

1. **`POST /produtos` é 1-a-1.** Não há bulk. Com 3 rps → ~6 min/1k itens no melhor caso. Use fila com retry.
2. **`gtin` (EAN) é validado** com dígito verificador. Pré-valide no parser.
3. **`ncm` é validado** contra tabela oficial. Pré-valide.
4. **`midia.imagens.externas`** — falha de URL não falha o produto, retorna em `warnings[]`. Loggar.
5. **`PUT /produtos` é replace**, não merge. Pra alterar 1 campo: GET → mutate → PUT.
6. **`marca` é string** — sem dedup pela API; padronize no parser local.
7. **`categorias/produtos` não cria árvore numa chamada** — encadeie POSTs com `categoriaPai.id`.
8. **`grupos-produtos` exige pai** — não dá pra criar raiz via API.
9. **`POST /produtos` retorna `warnings[]`** mesmo no sucesso — não ignore.
10. **Datas em query**: SEMPRE com zero-padding (`2026-05-01`, não `2026-5-1`). O SDK não-oficial tem bug aqui.
11. **`variacoes: []`** mesmo quando `formato="S"` — TypeScript do SDK exige, e evita 400 esporádico.
12. **Headers obrigatórios:** `Authorization: Bearer ...`, `Content-Type: application/json`, `Accept: application/json`.
13. **Paginação não retorna total** — itere `pagina` até `data` vazio ou `data.length < limite`.
14. **`CEST` é validado contra tabela oficial** (não basta ter 7 dígitos). CSVs típicos têm exemplos fake como `11.111.11` que retornam 400 `VALIDATION_ERROR / fields[].element=cest`. Omita o campo se não tiver CEST real.
15. **Categoria raiz vem como `categoriaPai: { id: 0 }`** no GET (não `null`!). Pra comparar com `parent_id=None` na sua lógica de upsert, normalize: `parent_id_real = None if categoriaPai.id in (0, None) else categoriaPai.id`. Sem isso, o GET nunca encontra categorias raiz existentes e você tenta recriar (e leva 400 "Já existe categoria de mesmo nível").
16. **Idempotência por SKU validada em produção:** `GET /produtos?codigo=X&limite=1` → se `data[]` não vazio, `PUT /produtos/{id}` (replace completo); senão `POST /produtos`.

---

## 6. Próximos passos pra MCP virtualization

Cada endpoint vira uma tool MCP:
- `bling_produtos_create`, `bling_produtos_get`, `bling_produtos_list`, `bling_produtos_update`, `bling_produtos_delete`, `bling_produtos_change_situation` (...)
- Idem pra todas 43 entidades → ~200 tools

Camada compartilhada:
- Token bucket (3 rps)
- Retry exponencial (429, 5xx)
- OAuth refresh automático
- Logging com correlation ID
- Idempotência por `codigo` (SKU) no `produtos_create` — checar existência antes do POST
