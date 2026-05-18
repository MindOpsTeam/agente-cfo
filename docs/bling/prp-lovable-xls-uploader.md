# PRP — App Lovable: XLS → Bling (MVP)

**Goal:** Usuário faz upload de uma planilha. Cada linha vira um produto no Bling. Tela mostra resultado linha-a-linha com link pra ver no painel do Bling.
**Stack:** Lovable Cloud (Next.js + Supabase + Edge Functions).
**Escopo:** MVP single-user (Diego/Solvicci). Multi-tenant fica pra v2.
**Tempo estimado:** 1 dia Lovable AI.

---

## Contexto crítico

- **API do Bling v3 base URL:** `https://api.bling.com.br/Api/v3` (host `api`, NÃO `www`)
- **OAuth endpoints:** `https://www.bling.com.br/Api/v3/oauth/{authorize,token}` (host `www`)
- **Auth:** Bearer JWT no header `Authorization`. Token expira em 6h. Refresh dura 30 dias com rotação.
- **Credenciais já capturadas:** access_token + refresh_token + client_id + client_secret armazenados em `skills/bling/.env` e `skills/bling/tokens.json` localmente. PRECISAM ir pra Supabase Secrets.
- **Rate limit:** 3 req/s + 120k/dia. Aplicação DEVE throttar (token bucket ou setTimeout 350ms entre chamadas).
- **Doc completa da API:** `docs/bling/api-v3-endpoints-map.md` no mesmo repo.

---

## Schema da planilha suportado (CSV ou XLSX)

Coluna obrigatória: `nome`. Resto: opcional, mas quanto mais preencher, mais completo o cadastro.

| Coluna | Tipo | Default | Notas |
|---|---|---|---|
| `codigo` | string | — | SKU. Se preenchido, faz UPSERT (não cria duplicado) |
| `nome` | string | — | **Obrigatório** |
| `preco` | number | 0 | |
| `unidade` | string | `"UN"` | Texto livre: UN, PC, KG, M, L... |
| `tipo` | enum | `"P"` | "P"=Produto, "S"=Serviço |
| `situacao` | enum | `"A"` | "A"=Ativo, "I"=Inativo |
| `descricao_curta` | string | — | |
| `peso_liquido` | number | — | kg |
| `peso_bruto` | number | — | kg |
| `gtin` | string | — | EAN-13. Validado pelo Bling |
| `ncm` | string | — | 8 dígitos. Validado pelo Bling |
| `cest` | string | — | |
| `origem` | int (0-8) | 0 | Origem fiscal |
| `marca` | string | — | Texto livre |
| `categoria_path` | string | — | Caminho hierárquico separado por `>`. Ex: `"Eletrônicos > Celulares > Smartphones"`. App resolve/cria categorias. |
| `largura` | number | — | cm |
| `altura` | number | — | cm |
| `profundidade` | number | — | cm |
| `estoque_minimo` | number | — | |
| `estoque_maximo` | number | — | |
| `observacoes` | string | — | |

**Importante:** colunas não listadas são ignoradas (sem erro). Coluna em PT-BR ou EN-equivalente aceita (normalizar no parser).

---

## Telas

### 1. `/` — Upload
- Drop zone (drag-and-drop ou clique pra abrir file picker)
- Aceita `.xlsx` e `.csv`
- Mostra preview das primeiras 5 linhas com colunas mapeadas vs. ignoradas
- Botão "Importar para o Bling" → dispara batch
- Validação client-side:
  - Coluna `nome` presente em todas as linhas
  - `gtin` (se presente) é dígito-verificador EAN-13 válido (warning, não bloqueia)
  - `ncm` (se presente) tem 8 dígitos (warning, não bloqueia)

### 2. `/batch/[id]` — Status do batch
- Header: progresso `X / N processados`, tempo decorrido, ETA
- Tabela linha-a-linha:
  - `#`, `código`, `nome`, status (pending / processing / created / updated / failed), `id_bling`, link `→` (abre `https://www.bling.com.br/index.php#produto/cadastro/{id}` em nova aba), warnings (badge se houver), error (popover se houver)
- Auto-refresh a cada 2s enquanto há `pending` ou `processing`
- Botão "Reprocessar falhas" no rodapé

### 3. `/config` — Conexão Bling
- Mostra status: conectado (account_name) / desconectado
- Botão "Reconectar Bling" → redirect pro fluxo OAuth (`/oauth/authorize` → callback → salva tokens em Supabase Secrets)
- Mostra último refresh, validade do token

---

## Backend (Supabase + Edge Functions)

### Tabelas

```sql
-- Supabase
create table bling_batches (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id),
  filename text,
  total_rows int,
  status text default 'pending',  -- pending|processing|done|failed
  created_at timestamptz default now(),
  finished_at timestamptz
);

create table bling_batch_items (
  id uuid primary key default gen_random_uuid(),
  batch_id uuid references bling_batches(id) on delete cascade,
  row_index int,
  payload jsonb,              -- linha original normalizada
  status text default 'pending',  -- pending|processing|created|updated|failed
  bling_id bigint,
  warnings jsonb default '[]'::jsonb,
  error text,
  attempted_at timestamptz,
  retry_count int default 0
);

create index on bling_batch_items(batch_id, status);

-- RLS: usuário só vê próprios batches
alter table bling_batches enable row level security;
alter table bling_batch_items enable row level security;
create policy "own_batches" on bling_batches for all using (auth.uid() = user_id);
create policy "own_items" on bling_batch_items for all using (
  exists(select 1 from bling_batches b where b.id = batch_id and b.user_id = auth.uid())
);
```

### Secrets Supabase (settings → Edge Functions → Secrets)
- `BLING_CLIENT_ID`
- `BLING_CLIENT_SECRET`
- `BLING_REDIRECT_URI` (URL pública do callback no Lovable: `https://{app}.lovable.app/api/bling/callback`)
- `BLING_ACCESS_TOKEN` (inicial, do `tokens.json`)
- `BLING_REFRESH_TOKEN` (inicial, do `tokens.json`)
- `BLING_TOKEN_EXPIRES_AT` (timestamp ISO)

### Edge Functions

#### `bling-oauth-callback` (GET)
- Recebe `?code=&state=`
- POST `https://www.bling.com.br/Api/v3/oauth/token` com `grant_type=authorization_code`
- Salva tokens em Supabase Secrets via management API ou em tabela `bling_credentials`
- Redirect pra `/config?success=1`

#### `bling-refresh-token` (cron: every 5 hours)
- Lê tokens atuais
- POST `/oauth/token` com `grant_type=refresh_token`
- Atualiza access_token + refresh_token (rotacionado) + expires_at
- **Não falha silenciosamente** — se 401, marca status "needs_reauth" e dispara notification email

#### `bling-process-batch` (POST, invocada após upload)
- Recebe `{ batch_id }`
- Lê todos os `bling_batch_items` com `status='pending'` em ordem
- Pra cada item:
  1. Marca `status='processing'`
  2. Throttle: garante ≥350ms desde última chamada Bling (token bucket simples)
  3. Se `codigo` preenchido: GET `/produtos?codigo={codigo}&limite=1` → se existir, PUT `/produtos/{id}`; senão, POST
  4. Se `categoria_path` preenchido: resolver hierarquia ANTES (helper `getOrCreateCategoryPath`)
  5. Monta payload conforme schema do Bling (ver mapeamento abaixo)
  6. Chama Bling
  7. Sucesso → marca `status='created'|'updated'`, `bling_id`, `warnings`
  8. Erro 4xx → marca `failed`, salva `error.description`
  9. Erro 5xx ou 429 → backoff exponencial (1s, 2s, 4s), max 3 tentativas
  10. 401 → chama `bling-refresh-token` e retenta uma vez
- Atualiza `bling_batches.status` quando todos os items terminarem
- **Limite de duração de Edge Function (Supabase: 50s, Lovable Cloud pode ter maior):** se batch > 100 items, processar em chunks e re-invocar via `setTimeout 0` ou trigger DB.

#### `bling-get-or-create-category-path` (helper interno)
- Recebe `["Eletrônicos", "Celulares", "Smartphones"]`
- Pra cada nível:
  - GET `/categorias/produtos?descricao={X}` (Bling não filtra por pai via query — paginar e filtrar localmente)
  - Se não acha: POST `/categorias/produtos` `{ descricao: X, categoriaPai: { id: parent_id } }`
- Retorna `id_categoria_folha`
- Cachear resultados em memória durante o batch

### Mapeamento XLS row → payload Bling

```javascript
function buildBlingPayload(row, contextIds) {
  const body = {
    nome: row.nome,
    tipo: row.tipo || "P",
    situacao: row.situacao || "A",
    formato: "S",          // sempre simples no MVP
    variacoes: [],
    codigo: row.codigo || undefined,
    preco: parseFloat(row.preco) || 0,
    unidade: row.unidade || "UN",
    descricaoCurta: row.descricao_curta || undefined,
    pesoLiquido: parseFloat(row.peso_liquido) || undefined,
    pesoBruto: parseFloat(row.peso_bruto) || undefined,
    gtin: row.gtin || undefined,
    marca: row.marca || undefined,
    observacoes: row.observacoes || undefined,
  };
  if (contextIds.categoriaId) {
    body.categoria = { id: contextIds.categoriaId };
  }
  if (row.largura || row.altura || row.profundidade) {
    body.dimensoes = {
      largura: parseFloat(row.largura) || undefined,
      altura: parseFloat(row.altura) || undefined,
      profundidade: parseFloat(row.profundidade) || undefined,
    };
  }
  if (row.ncm || row.cest || row.origem !== undefined) {
    body.tributacao = {
      ncm: row.ncm || undefined,
      cest: row.cest || undefined,
      origem: parseInt(row.origem) || 0,
    };
  }
  if (row.estoque_minimo || row.estoque_maximo) {
    body.estoque = {
      minimo: parseFloat(row.estoque_minimo) || undefined,
      maximo: parseFloat(row.estoque_maximo) || undefined,
    };
  }
  return body;
}
```

---

## Critério de aceite (DoD)

- [ ] Subir CSV/XLSX de teste com 50 linhas (mix de simples e completos)
- [ ] Todas as 50 linhas aparecem na tabela de status
- [ ] No mínimo 45/50 viram produtos no Bling (>90% sucesso assumindo XLS válido)
- [ ] Linhas com `gtin`/`ncm` inválidos viram `failed` com erro do Bling visível na UI
- [ ] Linhas que falharam podem ser reprocessadas
- [ ] Categorias hierárquicas são criadas se não existirem
- [ ] Reabrir o app após upload mostra histórico do batch
- [ ] Link "→" leva ao produto no painel do Bling em nova aba
- [ ] Re-upload do MESMO arquivo com `codigo` preenchido = UPDATE, não duplica
- [ ] Token refresh roda automaticamente (validar deixando rodar 6h+)

---

## Não-objetivos (v2, não fazer agora)

- ❌ Multi-tenant (cada cliente conecta o Bling dele) — MVP é single-user
- ❌ Suporte a variações (formato="V")
- ❌ Suporte a kits/estruturas (formato="E")
- ❌ Upload de imagens (campo `midia.imagens.externas`)
- ❌ Vincular fornecedor por produto (`/produtos/fornecedores`) — usar planilha separada se precisar
- ❌ Anúncios em marketplaces (`/produtos/lojas`)
- ❌ Editar produtos pela UI — só via re-upload
- ❌ Webhook reverso do Bling pra detectar deletes externos
- ❌ Painel admin de logs/auditoria além da tabela de status

---

## Pegadinhas pra Lovable AI atentar

1. **Host das chamadas:** Bearer JWT só funciona em `api.bling.com.br`. OAuth em `www.bling.com.br`. NÃO confundir.
2. **Parser XLSX no Edge:** usar `xlsx` (npm) ou `exceljs`. Cuidado com Deno runtime (algumas libs não rodam) — testar `xlsx` em Deno antes ou fazer parse no client e mandar JSON pro Edge.
3. **Rate limit:** 3 req/s. Com category lookup + create, cada linha = 2-3 chamadas. 50 produtos = ~150 chamadas = ~50s mínimo. Mostrar progresso real.
4. **Categoria não filtra por pai via query** — paginar e filtrar localmente. Pra hierarquia profunda, cachear durante o batch.
5. **`warnings[]` no response do POST /produtos** — sempre exibir na UI mesmo no sucesso (imagens que falharam, ajustes).
6. **`PUT /produtos/{id}` é REPLACE, não MERGE** — pra UPSERT, fazer GET completo, mesclar campos do XLS, e enviar tudo.
7. **CORS:** Bling API não suporta CORS browser-side. TODAS as chamadas Bling DEVEM passar pelo Edge Function.
