# PRP — Refator MCP Bling pra Completar Cobertura + Workflow XLS

**Target file:** `/Users/barboza/agente-cfo/skills/bling/mcp_server.py` (atual: ~1500 linhas, 116 tools)
**Goal:** Completar cobertura das 43 entidades da API Bling v3 + habilitar o caso de uso "upload XLS → cadastro automatizado de produtos com tributação e fornecedores".
**Tempo estimado:** 2-3 dias OpenClaw.
**Base atual:** sólida (auth, refresh, retry, MCP framework). Não reescrever — estender.

---

## Contexto crítico que NÃO pode quebrar

1. **Host das chamadas autenticadas:** `https://api.bling.com.br/Api/v3` (NÃO `www`). Já está hardcoded em `BlingClient.BASE_URL`. Manter.
2. **OAuth `/oauth/token` permanece em `www.bling.com.br/Api/v3/oauth/token`** — não confundir.
3. **Refresh token rotaciona** a cada uso — `_save_tokens()` já cuida. Manter persistência em `~/.openclaw/secrets/bling.env`.
4. **Rate limit oficial Bling:** 3 req/s + 120k req/dia. Esta refator DEVE adicionar token bucket.
5. **Doc de endpoints completos:** `/Users/barboza/agente-cfo/docs/bling/api-v3-endpoints-map.md` — fonte de verdade pros paths e schemas.

---

## Tarefa 1 — Estender schema de `bling_criar_produto` e `bling_atualizar_produto`

### Estado atual (linha 485-490 aprox)
```python
body = {'nome': args['nome'], 'preco': args['preco']}
if args.get('codigo'): body['codigo'] = args['codigo']
if args.get('unidade'): body['unidade'] = args['unidade']
if args.get('tipo'): body['tipo'] = args['tipo']
```

### Refator
Aceitar TODO o schema do `POST /produtos` da API v3. Trabalhar em níveis:

**Root (raiz):**
- Obrigatórios: `nome`, `tipo` ("S"|"P"|"N"), `situacao` ("A"|"I"), `formato` ("S"|"V"|"E"), `variacoes` (array, pode ser vazio)
- Opcionais: `codigo`, `preco`, `descricaoCurta`, `dataValidade`, `unidade`, `pesoLiquido`, `pesoBruto`, `volumes`, `itensPorCaixa`, `gtin`, `gtinEmbalagem`, `tipoProducao` ("P"|"T"), `condicao` (0|1|2), `freteGratis` (bool), `marca`, `descricaoComplementar`, `linkExterno`, `observacoes`, `actionEstoque` ("Z"|"T")
- Objetos por referência: `categoria.id`, `linhaProduto.id`

**Objetos aninhados (opcionais, todos):**
- `estoque`: `minimo`, `maximo`, `crossdocking`, `localizacao`
- `dimensoes`: `largura`, `altura`, `profundidade`, `unidadeMedida` (number)
- `tributacao`: `origem` (0-8), `nFCI`, `ncm`, `cest`, `codigoListaServicos`, `spedTipoItem`, `codigoItem`, `percentualTributos`, `valorBaseStRetencao`, `valorStRetencao`, `valorICMSSubstituto`, `codigoExcecaoTipi`, `classeEnquadramentoIpi`, `valorIpiFixo`, `codigoSeloIpi`, `valorPisFixo`, `valorCofinsFixo`, `codigoANP`, `descricaoANP`, `percentualGLP`, `percentualGasNacional`, `percentualGasImportado`, `valorPartida`, `tipoArmamento` (0|1), `descricaoCompletaArmamento`, `dadosAdicionais`, `grupoProduto.id`
- `midia.imagens.externas[].link` + `midia.video.url`
- `estrutura` (quando formato="E"): `tipoEstoque`, `lancamentoEstoque`, `componentes[].produto.id`, `componentes[].quantidade`
- `variacoes[]` (quando formato="V"): mesma estrutura do produto raiz + `variacao.nome`, `variacao.ordem`, `variacao.produtoPai.cloneInfo`
- `camposCustomizados[]`: `idCampoCustomizado`, `idVinculo?`, `valor?`, `item?`

### Schema MCP da tool
- Em vez de listar 50 params escalares, aceitar UM param `produto` (object) com sub-objetos. Documentar inline com schema completo nos `inputSchema`.
- Validação client-side antes do POST: `nome`, `tipo`, `situacao`, `formato`, `variacoes` obrigatórios; warnings se `gtin` parecer inválido (dígito verificador EAN-13).

### Response
- Retornar `{ id, warnings, raw }` — `warnings` é crucial (imagens que falharam, ajustes auto-feitos pelo Bling).

---

## Tarefa 2 — Virtualizar 16 entidades faltantes

Adicionar tools para cada (CRUD completo onde aplicável). Usar exatamente os paths da seção 2 do `api-v3-endpoints-map.md`. Priorizar pra workflow XLS:

### Prioridade ALTA (bloqueante pro XLS)
- **Grupos-Produtos** (`/grupos-produtos`): list, get, create, update, delete, deleteMany — payload: `{ nome, grupoProdutoPai.id }`. ⚠️ `grupoProdutoPai.id` obrigatório.
- **Produtos-Fornecedores** (`/produtos/fornecedores`): list, get, create, update, delete — payload: `{ produto.id, fornecedor.id, descricao?, codigo?, precoCusto?, precoCompra?, padrao?, garantia? }`
- **Produtos-Lojas** (`/produtos/lojas`): list, get, create, update, delete — payload: `{ codigo, produto.id, loja.id, preco?, precoPromocional?, fornecedorLoja.id?, marcaLoja.id?, categoriasProdutos[].id? }`
- **Produtos-Variações** (`/produtos/variacoes/{idProdutoPai}`): find, changeAttributeName (PATCH), generateCombinations (POST)
- **Produtos-Estruturas** (`/produtos/estruturas`): get, addComponent (POST), changeComponent (PATCH), deleteComponents, delete, update
- **Canais-Venda** (`/canais-venda`): list, get, getTypes (suporte a `produtos/lojas`)

### Prioridade MÉDIA
- **Categorias-Lojas** (`/categorias/lojas`): CRUD completo
- **Categorias-Produtos**: ADICIONAR create, update, delete (hoje só LIST). ⚠️ não cria árvore; encadear `categoriaPai.id`.
- **Contas-Contábeis** (`/contas-contabeis`): list, get
- **Contatos-Tipos** (`/contatos/tipos`): list
- **Situações** (`/situacoes`): CRUD + sub-rotas (modulos/transicoes)
- **Notificações** (`/notificacoes`): list, markRead

### Prioridade BAIXA (cobertura)
- Logísticas-Etiquetas, Logísticas-Objetos, Logísticas-Remessas, Logísticas-Serviços
- Usuários (validateHash, changePassword, recoverPassword)
- Campos-Customizados: ADICIONAR create, update, delete, getModules, getTypes, findModule

---

## Tarefa 3 — Reliability layer

### 3.1 Token bucket (3 rps)
- Implementar token bucket compartilhado no `BlingClient` (lock por instância).
- Antes de TODA chamada HTTP: `_throttle()` que dorme até liberar token.
- Capacidade: 3 tokens, refil 3 por segundo.
- Burst: permitir até 3 simultâneas, mas média mantém-se em 3 rps.

### 3.2 Detecção de 401 + reauth
- `http_request()` atual retry 429/503 mas NÃO trata 401.
- Adicionar: se HTTP 401, chamar `_refresh()` forçado uma vez e re-tentar. Se 401 de novo, falhar com erro claro `"refresh_token expirou — reauthorize via oauth_helper.py"`.

### 3.3 Logging estruturado
- Adicionar correlation ID por chamada (UUID).
- Log JSON em stderr: `{ ts, correlation_id, tool, method, url, status, duration_ms, retry_count }`.
- Em caso de erro: log também o `error.message` da resposta Bling.

### 3.4 Bulk operations (deleteMany)
- Adicionar tools `bling_delete_many_*` para entidades que suportam: produtos, contatos, propostas, grupos-produtos, pedidos-vendas, ordens-producao (via DELETE /resource?ids=...).

---

## Tarefa 4 — Tools auxiliares pro workflow XLS

Adicionar 3 tools de alto nível que orquestram múltiplas chamadas:

### 4.1 `bling_produto_upsert_by_codigo`
Idempotência por SKU:
1. `GET /produtos?codigo={sku}&limite=1`
2. Se existe → `PUT /produtos/{id}` (update)
3. Se não existe → `POST /produtos` (create)
4. Retorna `{ id, action: "created"|"updated", warnings }`

### 4.2 `bling_categoria_get_or_create_path`
Resolve hierarquia "Eletrônicos > Celulares > Smartphones" em uma chamada:
1. Recebe array `["Eletrônicos", "Celulares", "Smartphones"]`
2. Para cada nível: GET com `descricao=X&categoriaPai.id=parent` → se não existe, POST
3. Retorna `idCategoria` da folha

### 4.3 `bling_xls_batch_status` (opcional, se houver state mgmt)
- Track de batches em arquivo local `~/.openclaw/state/bling-batches/{batch_id}.json`
- Tools: `start_batch`, `add_item`, `get_status`, `retry_failed`

---

## Tarefa 5 — Testes

Adicionar em `skills/bling/tests/`:

### 5.1 Smoke test (já existe, ampliar)
- GET /produtos com tokens reais
- POST /produtos completo (todos os campos opcionais preenchidos) → DELETE
- Validar warnings no response

### 5.2 Reliability tests
- Mock 429 → ver backoff funcionando
- Mock 401 → ver refresh + retry
- Burst de 10 requests → token bucket segura em 3 rps

### 5.3 Workflow XLS (e2e)
- Fixture XLS com 50 produtos (incluindo categorias hierárquicas, NCM válidos, GTINs válidos)
- Rodar `upsert_by_codigo` em batch
- Assert: 50 produtos no Bling, zero 429, zero crashes

---

## Critério de aceite (DoD)

- [ ] Todas 43 entidades têm pelo menos LIST + GET virtualizado
- [ ] Produtos: CRUD completo + estruturas + fornecedores + lojas + variações
- [ ] `bling_criar_produto` aceita schema completo (tributação, dimensões, mídia, estrutura, variações)
- [ ] Token bucket de 3 rps verificável em log
- [ ] Detecção 401 + refresh + retry
- [ ] Logging com correlation ID
- [ ] Upsert por SKU idempotente
- [ ] Categoria hierárquica resolvida em 1 chamada de tool
- [ ] Smoke test passa contra Bling real (conta Solvicci)
- [ ] Tools totalizam ~180-200 (de 116 atuais)

---

## Não-objetivos (explicitamente fora)

- ❌ Interface de upload XLS (será Lovable AI, frontend separado)
- ❌ Parser de XLS (será no frontend ou middleware separado)
- ❌ Validação fiscal complexa (NCM contra tabela oficial, CFOP por UF) — confiar no Bling
- ❌ Sandbox/mock do Bling — testar contra conta real
- ❌ Suporte a v2 da API — só v3
