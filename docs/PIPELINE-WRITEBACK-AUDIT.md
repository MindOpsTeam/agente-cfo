# PIPELINE-WRITEBACK-AUDIT.md — Sprint AUDIT-B

> **Gerado em:** 2026-05-20 07:44 UTC  
> **Escopo:** Gap analysis do pipeline WhatsApp/Telegram → Painel → ERP (write-back)  
> **Metodologia:** Leitura estática de código — sem modificações  
> **Auditor:** Pikachu / OpenClaw

---

## 1. Mapa do Fluxo Atual

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│ CAMINHO A — Evolution API / WhatsApp (novo, cross-channel)                        │
│                                                                                   │
│  Usuário (WA)                                                                     │
│      │ POST webhook                                                                │
│      ▼                                                                            │
│  edge fn: whatsapp-incoming-webhook/index.ts                                      │
│    • Valida X-Webhook-Secret contra evolution_config.webhook_secret               │
│    • Extrai instanceName, remoteJid, text                                         │
│    • fromMe=true → skip (não roteia msgs enviadas pelo número pareado)            │
│    • Forward → POST /incoming-message                                             │
│      │                                                                            │
│      ▼                                                                            │
│  edge fn: incoming-message/index.ts                          [arquivo central]    │
│    • Valida secret por canal (whatsapp_instances ou telegram_bots)                │
│    • Verifica receives_marcos_chat                                                 │
│    • Insere user msg → chat_messages (role='user')                               │
│    • Busca VPS online (instances.last_heartbeat < 5min)                          │
│    • Monta promptMsg INLINE (genérico — ver §4)                                   │
│    • Insere placeholder → chat_messages (role='marcos', status='pending')        │
│    • POST {ingress_url}/hooks/agent (fire-and-forget, timeout 20s)               │
│      │                                                                            │
│      ▼                                                                            │
│  OpenClaw (Marcos) na VPS                                                        │
│    • Recebe promptMsg inline                                                      │
│    • Raciocina e usa ferramentas (bash, MCP servers)                             │
│    • Chama: python3 erp_gateway.py <cmd>                                         │
│    • Chama: bash panel_post_reply.sh <channel> <ext_id> <thread_id> <run_id>    │
│      │                                                                            │
│      ▼                                                                            │
│  panel_post_reply.sh                           ← GAP CRÍTICO (§5.D)             │
│    case "whatsapp" → AVISO "tipo desconhecido" → NÃO envia pelo canal           │
│    case "telegram" → AVISO "tipo desconhecido" → NÃO envia pelo canal           │
│    case "panel"    → só grava no painel (panel_reply.sh)                         │
│      │                                                                            │
│      ▼                                                                            │
│  edge fn: chat-marcos-reply/index.ts                                             │
│    • Atualiza chat_messages (pending → sent) com conteúdo da resposta           │
│    • Supabase Realtime notifica painel web                                       │
└───────────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────────────────┐
│ CAMINHO B — wacli (legado, VPS-only)                                             │
│                                                                                   │
│  Usuário (self-chat WA)                                                          │
│      │ polling local                                                              │
│      ▼                                                                            │
│  wacli_inbound.py (daemon VPS)                                                   │
│    • Detecta msgs do dono via wacli messages list --json                         │
│    • Dedup por msg.id + cursor (seen_ids, last_ts)                               │
│    • Detecta confirm_token pendente → automation-confirm edge fn                 │
│    • POST /hooks/agent com: [WA_INBOUND] from_jid=... + instrução conversa.md  │
│      │                                                                            │
│      ▼                                                                            │
│  OpenClaw (Marcos) na VPS                                                        │
│    • Carrega prompts/conversa.md (completo — inclui intent de WRITE)            │
│    • Usa erp_gateway.py / crm_gateway.py / cobranca_gateway.py                   │
│    • Responde via bash _shared.sh + wacli send (JID direto)                     │
└───────────────────────────────────────────────────────────────────────────────────┘
```

**Dois fluxos paralelos coexistem.** Caminho A é o novo (suporta múltiplos canais via
painel), Caminho B é o legado (self-chat WA via daemon local). Eles têm contratos
de prompt, dedup e reply diferentes.

---

## 2. Tabelas Disponíveis no Painel (Supabase)

Inventário completo via migrations + edge functions:

| Tabela | Propósito | Relevante para write-back? |
|--------|-----------|---------------------------|
| `chat_messages` | Histórico unificado de conversa (user/marcos/system) | ✅ Sim (armazena diálogo) |
| `instances` | VPS registradas (heartbeat, ingress_url, hooks_token) | — |
| `events` | Log de eventos do sistema (omie_error, wa_status, etc.) | ⚠️ Parcialmente |
| `instance_metrics` | Métricas de observabilidade (metrics_publisher.py) | — |
| `evolution_config` | Config Evolution API (webhook_secret, active) | — |
| `whatsapp_instances` | Instâncias WA por canal (receives_marcos_chat) | — |
| `telegram_bots` | Bots Telegram (webhook_secret, receives_marcos_chat) | — |
| `whatsapp_status` | Status de conexão WA | — |
| `omie_errors` | Erros de API Omie (derivado de events) | — |
| `user_onboarding` | Estado do wizard de setup | — |
| `installer_tokens` | One-time tokens de setup | — |
| `integration_credentials` | Credenciais de integração ativas | — |
| `supabase_projects` | Projetos Supabase do usuário | — |
| `automation_*` | Motor de automações do painel | ⚠️ Parcialmente |

### ❌ Tabela `expenses` / `transactions` / `cfo_events`: NÃO EXISTE

**Gap confirmado:** Não há nenhuma tabela no schema do painel para registrar
lançamentos financeiros feitos via chat (despesas, receitas, pagamentos executados).
O dashboard só visualiza dados via reports-* (que leem diretamente dos ERPs).

Consequência: quando Marcos lança uma despesa no Omie via `create_payable`,
o painel só reflete esse dado quando o próximo relatório rodar (pull do ERP) —
não há espelhamento imediato no banco do painel.

### ⚠️ Tabela `events` — uso parcial
A edge fn `event/index.ts` aceita type arbitrário, mas só trata derivados para
`omie_error` e `wa_status_*`. Um `write_executed` gravaria na tabela `events`
como payload JSON, mas **não há dashboard ou query que o consuma**.

---

## 3. Análise de Prompts — Intent de WRITE

### Caminho A (incoming-message — promptMsg inline)

```
Você é Marcos, CFO virtual. Responda em português, claro e sem rodeios.
Use ferramentas (bash, scripts, MCP servers) se precisar consultar dados reais.
```

**Diagnóstico:** Prompt genérico. Não menciona:
- Detecção de intent (leitura vs. write)
- Protocolo de confirmação antes de write
- Schema esperado para extração de valor/fornecedor/data
- Qual ferramenta chamar (`erp_gateway.py create_payable`)
- Que rota de resposta usar por canal (WA vs Telegram vs painel)

Marcos **pode** responder inteligentemente porque o modelo conhece o domínio,
mas não tem contrato formal. Resultado: comportamento inconsistente entre
sessões/modelos.

### Caminho B (wacli_inbound.py → conversa.md)

`conversa.md` contém:
- ✅ Tabela completa de intents de LEITURA com comandos mapeados
- ✅ Protocolo obrigatório de WRITE com 6 etapas (leitura → rascunho → confirmação → execução → confirm → audit log)
- ✅ Protocolo de cobrança ativa (Asaas/Iugu) com 6 etapas
- ✅ Regras de formato WhatsApp (máx 600 chars)
- ✅ Tratamento de ambiguidade ("Pergunte, nunca chute")
- ✅ Audit log obrigatório via `_panel_event "write_executed"`

**Gap:** `conversa.md` não é carregado no Caminho A (promptMsg é inline, não referencia o arquivo).

---

## 4. GAP ANALYSIS — 7 Gaps + 3 Adicionais

---

### GAP 1 — Intent Detection Ausente no Caminho A
**Status: FALTA (crítico)**

**O que existe:** conversa.md tem tabela completa de intents com comandos mapeados (Caminho B).

**O que falta:** promptMsg em `incoming-message/index.ts` (Caminho A) é 3 linhas genéricas.
Não há instrução para Marcos extrair `{amount, supplier, due_date, category}` de
"gastei 50 reais com Uber", nem para chamar `erp_gateway.py create_payable`.

**Fix sugerido (P0):**
Adicionar ao promptMsg em `incoming-message/index.ts` uma referência ao arquivo de instruções:

```typescript
const promptMsg = `[INCOMING_MESSAGE]
Canal: ${channelLabel}
Phone/Chat: ${externalId}
Usuário: ${text}
${contextBlock}
Instruções completas em: $HOME/.openclaw/workspace/skills/agente-cfo/prompts/conversa.md
Leia e siga antes de responder.
...`
```

Ou injetar o conteúdo do arquivo diretamente no promptMsg (mais robusto).

---

### GAP 2 — Espelhamento no Painel: Tabela de Lançamentos Inexistente
**Status: FALTA (estrutural)**

**O que existe:** `events` como log genérico de sistema. Reports-* leem direto do ERP.

**O que falta:**
- Tabela `cfo_write_events` (ou `transactions_mirror`) no Supabase para registrar
  lançamentos feitos via chat com: `{channel, thread_id, run_id, action, erp, erp_id, amount, supplier, due_date, category, confirmed_at, status}`
- Edge function para Marcos gravar esse mirror via X-Panel-Token
- Widget no dashboard que mostre "Últimas ações feitas via chat"

**Fix sugerido (P1):**
1. Migration: `CREATE TABLE cfo_write_events (...)`
2. Edge fn: `POST /cfo-write-event` (X-Panel-Token, aceita payload de write)
3. Marcos chama essa edge fn após toda confirmação de write (via bash curl ou _shared.sh)
4. Dashboard: lista últimas 10 ações via chat com status (success/error)

---

### GAP 3 — Tool MCP de Write Não Exposta
**Status: PARCIAL**

**O que existe:**
- `erp_gateway.py create_payable` funciona via bash subprocess no Caminho B
- 7 ERPs têm `create_payable/receivable` implementados nos clients (omie, bling, contaazul, granatum, nibo, vhsys)
- Tiny: `create_payable` retorna `{"error": "not_supported"}` (API v2 não suporta)
- `skills/agente-cfo/` NÃO TEM `mcp_server.py` (confirmado na AUDIT-A)

**O que falta:**
- `mcp_server.py` para a skill `agente-cfo` que exponha tools como:
  - `cfo_create_payable(amount, supplier, due_date, category)`
  - `cfo_create_receivable(amount, customer, due_date, category)`
  - `cfo_get_balance()`, `cfo_list_payables()`, etc.
- Sem esse MCP, Marcos acessa o erp_gateway apenas via `bash` — funciona mas
  é menos tipado, sem validação de schema JSON e sem rastreabilidade via tools/list

**Fix sugerido (P2):**
Criar `skills/agente-cfo/mcp_server.py` que wrapeie `erp_gateway.py` e `crm_gateway.py`
como tools MCP com schema Pydantic validado.

---

### GAP 4 — Confirmação Estruturada: Sem Padrão no Canal de Origem
**Status: PARCIAL**

**O que existe:** conversa.md define formato de confirmação para Caminho B (WA auto-chat):
```
Confirme:
PAGAR
Fornecedor: [nome]
...
Responda SIM pra confirmar ou NAO pra cancelar.
```

**O que falta:**
- No Caminho A, não há instrução para usar esse padrão
- `panel_post_reply.sh` não envia pelo canal externo (WA/Telegram) — só grava no painel
- O dono não recebe o draft de confirmação via WhatsApp/Telegram; só via painel web
- Se o dono responder "SIM" no WA, a mensagem chega via `whatsapp-incoming-webhook`
  → `incoming-message` → novo turn do Marcos — mas Marcos não sabe que está
  aguardando confirmação de um write anterior (sem estado de sessão no Caminho A)

**Fix sugerido (P0):**
- `panel_post_reply.sh` precisa implementar os cases `whatsapp` e `telegram`
  chamando os respectivos scripts de envio (evolution API ou telegram bot API)
- Estado de confirmação pendente precisa ser persistido (chat_messages metadata
  ou arquivo de state na VPS) para que o próximo inbound seja reconhecido como reply

---

### GAP 5 — Idempotência: Risco de Duplo Lançamento
**Status: FALTA**

**O que existe:**
- `wacli_inbound.py` tem dedup robusto por `msg.id` + `seen_ids` (cursor local)
- `proactive_rules` têm dedup por `dedup_key` + cooldown_hours

**O que falta no Caminho A:**
- `incoming-message` insere user msg + placeholder Marcos mas não persiste
  nenhum `dedup_key` para o write pendente
- Se o hook para a VPS falha (timeout 20s), `marcosMsg` fica em `status='pending'`
  forever — não há retry com dedup
- Se o dono reenviar a mensagem (por não receber resposta), um segundo run é
  disparado. Se o primeiro run já executou o write no ERP mas não conseguiu
  responder, o segundo run pode fazer o write de novo

**Fix sugerido (P1):**
- Gerar `write_dedup_key = hash(thread_id + content + date)` antes de executar write
- Checar na tabela `cfo_write_events` (a ser criada — GAP 2) se já existe entrada
  com esse dedup_key nas últimas 24h
- Se existir: responder "Esse lançamento já foi registrado (id=X). Quer criar outro?"

---

### GAP 6 — Extração de Entidade: "Gastei 50 com Uber"
**Status: DEPENDE DO MODELO**

**O que existe:** Marcos usa Sonnet 4.6 — capaz de inferir `amount=50, supplier=Uber`.

**O que falta:**
- Não há few-shot explícito no promptMsg (Caminho A) para extração de entidade
- Não há schema de validação: Marcos pode inferir `due_date=hoje` sem avisar,
  ou inferir `category=Transporte` sem confirmar — comportamento não garantido
- `create_payable` exige: `amount`, `due_date`, `supplier`. Se Marcos chamar sem
  `due_date`, `erp_gateway.py` pode falhar com erro de argumento

**Fix sugerido (P1):**
Adicionar ao promptMsg (ou conversa.md) um bloco de extração estruturada:

```
Quando o usuário mencionar despesa/receita sem data, assuma hoje (DATA_HOJE).
Antes de criar qualquer lançamento, mostre o rascunho:
  "Entendi: R$50 pago para Uber, categoria Transporte, data de hoje (20/05).
   Confirma? (SIM/NÃO)"
```

---

### GAP 7 — Canais SPECIAL: evolution-api, telegram, supabase
**Status: PARCIAL / BLOQUEADO**

#### evolution-api
- `skills/evolution-api/scripts/` contém apenas `__pycache__` (sem fonte .py)
- Não há `mcp_server.py`
- O fluxo de inbound já funciona via `whatsapp-incoming-webhook/index.ts` → `incoming-message`
- O fluxo de **outbound** (Marcos → WA) está **bloqueado**: `panel_post_reply.sh` não implementa o case `whatsapp` (cai no wildcard `*` e só loga aviso)
- Não há `_send_whatsapp.sh` no workspace de skills
- Apenas `wacli_inbound.py` + `_shared.sh` (_to_jid) dão suporte a envio, mas são
  usados pelo Caminho B (wacli/self-chat), não pelo Caminho A (Evolution API)

**Fix sugerido (P0):**
Implementar case `whatsapp` em `panel_post_reply.sh`:
```bash
whatsapp)
    bash "$WORKSPACE/evolution-api/scripts/send_message.sh" \
      "$CHANNEL_NAME" "$EXTERNAL_ID" "$REPLY"
    ;;
```
E criar `skills/evolution-api/scripts/send_message.sh` que use a Evolution API REST
para enviar mensagem na instância/número corretos.

#### telegram
- `skills/telegram/scripts/` contém apenas `__pycache__` (sem fonte .py)
- Não há script de envio de resposta Telegram
- `panel_post_reply.sh` não implementa case `telegram`
- Edge fn `incoming-message/index.ts` lê `telegram_bots` e roteia, mas o retorno
  de Marcos nunca chega ao usuário Telegram

**Fix sugerido (P0):**
Implementar case `telegram` em `panel_post_reply.sh` + criar `skills/telegram/scripts/send_message.sh`
usando Bot API: `POST https://api.telegram.org/bot{TOKEN}/sendMessage`

#### supabase (npm package)
- `npx @supabase/mcp-server-supabase@latest` está instalado em cache npx
- Ao receber `--help`, retorna erro (não aceita esse flag) — esperado para servidor MCP stdio
- `supabase_sync.py` (daemon) sincroniza projetos via painel → openclaw.json
- **Handshake JSON-RPC não testado** porque o package requer `SUPABASE_URL` +
  `SUPABASE_SERVICE_ROLE_KEY` válidos para iniciar
- Status do daemon: não verificável localmente (roda na VPS)

**Fix sugerido (P2):**
Criar `skills/supabase/tests/handshake_test.js` que rode o handshake Node.js com
credenciais dummy e capture o resultado de `initialize` + `tools/list`.

---

### GAP 8 — Dois Fluxos Paralelos Sem Documentação de Convivência
**Status: RISCO DE MANUTENÇÃO**

`wacli_inbound.py` (Caminho B) e `whatsapp-incoming-webhook` (Caminho A) podem
ambos estar ativos ao mesmo tempo na mesma VPS, processando a mesma mensagem do
dono duas vezes: uma vez via self-chat polling, outra via webhook Evolution → painel.

Não há flag ou mutex que impeça os dois paths de disparar simultaneamente para a
mesma mensagem.

**Fix sugerido (P2):**
Documentar política de convivência: se Evolution API estiver ativa, desativar `wacli_inbound.py`.
Ou: adicionar dedup global por `thread_id:msg_text:timestamp_window` no `/hooks/agent`.

---

### GAP 9 — panel_post_reply.sh: Assinatura Incorreta vs. conversa.md
**Status: BUG**

`conversa.md` instrui Marcos a chamar:
```bash
bash panel_post_reply.sh "<channel>" "<external_id>" "<reply>" [thread_id] [run_id]
```

Mas `incoming-message/index.ts` monta o promptMsg como:
```typescript
bash panel_post_reply.sh "${channel}" "${externalId}" "${threadId}" "${runId}" "<sua resposta>"
```

**Ordem dos argumentos é diferente:**
- conversa.md: `channel external_id reply [thread_id] [run_id]`
- promptMsg inline: `channel external_id thread_id run_id <resposta>`

O script `panel_post_reply.sh` usa `$1=CHANNEL, $2=EXTERNAL_ID, $3=REPLY, $4=THREAD_ID, $5=RUN_ID`.

Resultado: quando Marcos segue o promptMsg do Caminho A, `REPLY=$THREAD_ID`
e `THREAD_ID=$RUN_ID` — a resposta enviada ao painel é o `thread_id` string,
não o texto da resposta.

**Fix sugerido (P0):** Corrigir o promptMsg em `incoming-message/index.ts`:
```typescript
bash $HOME/.openclaw/workspace/skills/agente-cfo/scripts/panel_post_reply.sh \
  "${channel}" "${externalId}" "<sua resposta>" "${threadId}" "${runId}"
```

---

### GAP 10 — Tiny: create_payable Não Suportado
**Status: CONHECIDO, documentado**

`tiny_client.py` retorna `{"error": "not_supported"}` para `create_payable` e
`create_receivable`. Marcos precisa saber disso e informar ao usuário Tiny.

Já está documentado no próprio client. Mas conversa.md não menciona esse edge case.
Se o dono de empresa com Tiny disser "gastei R$50 com Uber", Marcos tentará
`erp_gateway.py create_payable` e receberá erro — sem instrução sobre o que dizer.

**Fix sugerido (P2):** Adicionar ao conversa.md:
```
Se erp_gateway.py retornar {"error": "not_supported"}: informe ao dono que
[ERP] não suporta essa operação via API e sugira fazer manualmente.
```

---

## 5. Cenário Canônico: "Gastei R$50 com Uber" — Passo a Passo

### Usuário no WhatsApp (Caminho A — novo)

| Etapa | O que acontece HOJE | Status |
|-------|---------------------|--------|
| 1. Usuário digita "Gastei 50 reais com Uber" no WA | Evolution API recebe a msg | ✅ OK |
| 2. Evolution dispara webhook → whatsapp-incoming-webhook | Valida secret, extrai text | ✅ OK |
| 3. Forward → incoming-message | Valida canal, insere em chat_messages | ✅ OK |
| 4. Busca VPS online | Verifica last_heartbeat < 5min | ✅ OK (se VPS ativa) |
| 5. Monta promptMsg | Prompt genérico sem intent de write | ❌ GAP 1 |
| 6. Dispara POST /hooks/agent | Fire-and-forget, timeout 20s | ✅ OK |
| 7. Marcos recebe prompt | Sem instrução de extração nem protocolo write | ❌ GAP 1 |
| 8. Marcos infere amount=50, supplier=Uber (modelo) | Possível mas não garantido | ⚠️ GAP 6 |
| 9. Marcos chama erp_gateway create_payable | Funciona via bash | ✅ OK (se ERP ≠ Tiny) |
| 10. Lançamento criado no Omie (ex: id=4882) | Dado no ERP | ✅ OK |
| 11. Painel espelha o lançamento | **NÃO HÁ tabela de espelhamento** | ❌ GAP 2 |
| 12. Marcos chama panel_post_reply.sh com ordem errada de args | REPLY = thread_id | ❌ GAP 9 |
| 13. panel_post_reply.sh case "whatsapp" | Cai no wildcard, só loga AVISO | ❌ GAP 7 |
| 14. Usuário recebe resposta no WA | **NÃO RECEBE** | ❌ GAP 7 |
| 15. Usuário reenvia a msg | Segundo run → risco de duplo lançamento | ❌ GAP 5 |

**Diagnóstico:** O cenário canônico tem 5 pontos de falha críticos no Caminho A.
O ERP recebe o lançamento (etapa 10) mas o usuário não recebe confirmação (etapa 14)
e o painel não registra (etapa 11).

### Usuário no WhatsApp (Caminho B — wacli legado)

| Etapa | O que acontece HOJE | Status |
|-------|---------------------|--------|
| 1. Usuário digita "Gastei 50 reais com Uber" no self-chat | wacli polling detecta | ✅ OK |
| 2. wacli_inbound.py dedup por msg.id | Não reprocessa | ✅ OK |
| 3. dispatch_to_agent via /hooks/agent | Inclui JID + instrução conversa.md | ✅ OK |
| 4. Marcos carrega conversa.md | Protocolo write completo carregado | ✅ OK |
| 5. Marcos detecta intent WRITE | Via tabela de intents do conversa.md | ✅ OK |
| 6. Marcos rascunha confirmação e envia via wacli | Usuário vê no WA | ✅ OK |
| 7. Usuário responde "SIM" | wacli_inbound.py detecta reply | ✅ OK |
| 8. Marcos executa create_payable | ERP criado | ✅ OK |
| 9. Marcos confirma via wacli | Usuário recebe "✅ Lançado R$50 em Omie (id=X)" | ✅ OK |
| 10. Marcos emite _panel_event "write_executed" | Grava em events (payload JSON) | ⚠️ Parcial (sem dashboard) |
| 11. Painel espelha o lançamento | **Não há tabela de espelhamento** | ❌ GAP 2 |

**Diagnóstico:** Caminho B funciona end-to-end para o cenário canônico **exceto** pelo
espelhamento no painel (GAP 2). A experiência do usuário está completa.

---

## 6. Tabela de Priorização de Sprints

| # | Gap | Prioridade | Impacto | Esforço estimado |
|---|-----|:---:|---------|-----------------|
| 9 | Ordem de args em panel_post_reply.sh / promptMsg | **P0** | Resposta de Marcos chega corrompida ao painel | 30min (1 linha) |
| 7a | panel_post_reply.sh case whatsapp (Evolution API) | **P0** | Usuário WA nunca recebe resposta do Marcos | M (1-2h) |
| 7b | panel_post_reply.sh case telegram | **P0** | Usuário Telegram nunca recebe resposta | M (1-2h) |
| 1 | promptMsg em incoming-message sem intent de write | **P0** | Write-back via Caminho A não funciona de forma confiável | M (2-4h) |
| 4 | Confirmação de write não chega no canal externo | **P0** | Dono não pode confirmar "SIM/NÃO" pelo WA/Telegram | L (depende de GAP 7) |
| 2 | Tabela de espelhamento de lançamentos (cfo_write_events) | **P1** | Dashboard não mostra ações feitas via chat | L (migration + edge fn + UI) |
| 5 | Idempotência / dedup de write | **P1** | Risco de duplo lançamento no ERP | M (2-4h) |
| 6 | Few-shot de extração de entidade no prompt | **P1** | Extração inconsistente entre sessões | S (1-2h) |
| 8 | Dois fluxos paralelos (wacli + Evolution) sem dedup | **P2** | Mensagem processada duas vezes | M (2-4h) |
| 3 | MCP server para agente-cfo | **P2** | Marcos acessa ERP via bash (funcional mas menos tipado) | XL (novo mcp_server.py) |
| 10 | Tiny create_payable não suportado (edge case) | **P2** | UX ruim para usuários Tiny | S (1 linha em conversa.md) |
| 7c | Supabase MCP handshake (Node.js) | **P2** | Falta teste de sanidade para o canal BD | S (1 arquivo de teste) |

---

## 7. O Que Funciona Hoje (Resumo)

✅ **Caminho B (wacli legado) end-to-end:** Recebe, interpreta, confirma, executa, responde.  
✅ **16/16 MCPs Python em PASS** (AUDIT-A) — todas as ferramentas de ERP/CRM prontas.  
✅ **7/7 ERPs com `create_payable`** implementado (Tiny: stub com erro controlado).  
✅ **Protocolo de write** completo em `conversa.md` (6 etapas, audit log, dedup de alerta).  
✅ **Inbound cross-channel** via `incoming-message` + `whatsapp-incoming-webhook`.  
✅ **Histórico unificado** em `chat_messages` com Supabase Realtime.  

❌ **Outbound cross-channel:** Marcos não consegue enviar resposta de volta para WA/Telegram via Caminho A.  
❌ **Prompt do Caminho A:** Genérico, sem contrato de write.  
❌ **Espelhamento no painel:** Sem tabela de lançamentos via chat.  
❌ **Arg order bug:** promptMsg manda args fora de ordem para panel_post_reply.sh.

---

## 8. Dados de Ambiente

```
Repo:          /Users/barboza/agente-cfo (dev local)
Python venv:   .venv/bin/python3 (3.12, mcp==1.27.1)
Node/npx:      v25.8.1 / 11.11.0
Supabase pkg:  @supabase/mcp-server-supabase (em cache npx, sem --help flag)
Migrations:    5 arquivos (até 2026-05-15)
Edge functions: 38 funções mapeadas
Scripts agente-cfo: 40+ arquivos em scripts/
Data auditoria: 2026-05-20
```

---

## Status Pós-Implementação (Sprint IMPL-P0+P1)

| Gap | Fix | Status |
|-----|-----|--------|
| GAP 9 — arg order bug | FIX 1 | ✅ Fechado |
| GAP 7a — outbound WhatsApp | FIX 2 | ✅ Fechado |
| GAP 7b — outbound Telegram | FIX 3 | ✅ Fechado |
| GAP 1/4/6 — promptMsg + few-shot | FIX 4 | ✅ Fechado |
| GAP 4 — pending_write state | FIX 5 | ✅ Fechado |
| GAP 2 — cfo_write_events | FIX 6 | ✅ Fechado |
| GAP 5 — dedup | FIX 7 | ✅ Fechado |
| GAP 3 — MCP agente-cfo | FIX IMPL-P2 | ✅ Fechado (14 tools) |
| GAP 8 — dois fluxos paralelos | FIX IMPL-P2 | ✅ Fechado (hooks_dedup) |

Commits: ver `git log --oneline` após sprint.
