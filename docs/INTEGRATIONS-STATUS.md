# INTEGRATIONS-STATUS.md — Sprint AUDIT-A

> **Gerado em:** 2026-05-20 07:24 UTC  
> **Ambiente:** `/Users/barboza/agente-cfo` (repo dev local)  
> **Python:** `.venv/bin/python3` (Python 3.12, mcp==1.27.1)  
> **Protocolo MCP testado:** `2024-11-05`  
> **Critério PASS:** mcp_server.py existe + boot sem crash + initialize OK + tools/list ≥1 tool + tool_call retorna erro controlado (não traceback)

---

## Matriz de Status

| skill | mcp_server.py | boot | initialize | tools/list | tool_count | controlled_error | status | first_tool |
|-------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| asaas | ✅ | ✅ | ✅ | ✅ | 33 | ✅ | **PASS** | `asaas_cobrancas_listar` |
| bling | ✅ | ✅ | ✅ | ✅ | 116 | ✅ | **PASS** | `bling_saldo` |
| contaazul | ✅ | ✅ | ✅ | ✅ | 32 | ✅ | **PASS** | `contaazul_saldo` |
| granatum | ✅ | ✅ | ✅ | ✅ | 39 | ✅ | **PASS** | `granatum_saldo` |
| hubspot | ✅ | ✅ | ✅ | ✅ | 463 | ✅ | **PASS** | `hubspot_deals_listar` |
| iugu | ✅ | ✅ | ✅ | ✅ | 33 | ✅ | **PASS** | `iugu_cobrancas_listar` |
| kommo | ✅ | ✅ | ✅ | ✅ | 85 | ✅ | **PASS** | `kommo_leads_list` |
| mercado-livre | ✅ | ✅ | ✅ | ✅ | 27 | ✅ | **PASS** | `mercado_livre_pedidos_listar` |
| nibo | ✅ | ✅ | ✅ | ✅ | 40 | ✅ | **PASS** | `nibo_saldo` |
| nuvemshop | ✅ | ✅ | ✅ | ✅ | 35 | ✅ | **PASS** | `nuvemshop_pedidos_listar` |
| omie | ✅ | ✅ | ✅ | ✅ | 96 | ✅ | **PASS** | `omie_clientes_listar` |
| pipedrive | ✅ | ✅ | ✅ | ✅ | 144 | ✅ | **PASS** | `pipedrive_deals_listar` |
| piperun | ✅ | ✅ | ✅ | ✅ | 27 | ✅ | **PASS** | `piperun_deals_listar` |
| rd-station | ✅ | ✅ | ✅ | ✅ | 27 | ✅ | **PASS** | `rd_station_deals_listar` |
| tiny | ✅ | ✅ | ✅ | ✅ | 28 | ✅ | **PASS** | `tiny_saldo` |
| vhsys | ✅ | ✅ | ✅ | ✅ | 54 | ✅ | **PASS** | `vhsys_saldo` |
| evolution-api | — | — | — | — | — | — | **SPECIAL** | canal — scripts shell |
| telegram | — | — | — | — | — | — | **SPECIAL** | canal — scripts shell |
| supabase | — | — | — | — | — | — | **SPECIAL** | NPM (não Python) |

---

## Resumo Executivo

| Categoria | Contagem |
|-----------|----------|
| **PASS** (todos critérios ✅) | **16 / 16** Python MCPs |
| **FAIL** (algum critério ✗) | **0** |
| **SPECIAL** (não-Python ou canais) | **3** (evolution-api, telegram, supabase) |
| **Total skills auditadas** | **19** |

**Resultado: 16/16 PASS — nenhum bug de boot encontrado. Zero correções necessárias.**

---

## Detalhamento por Skill

### ✅ Skills em PASS (16)

Todas as 16 skills Python passaram em todos os 5 critérios:

| skill | tools expostas | categoria |
|-------|:-:|---|
| asaas | 33 | cobrança |
| bling | 116 | ERP/e-commerce |
| contaazul | 32 | financeiro |
| granatum | 39 | financeiro |
| hubspot | 463 | CRM |
| iugu | 33 | cobrança |
| kommo | 85 | CRM |
| mercado-livre | 27 | marketplace |
| nibo | 40 | financeiro/contábil |
| nuvemshop | 35 | e-commerce |
| omie | 96 | ERP |
| pipedrive | 144 | CRM |
| piperun | 27 | CRM |
| rd-station | 27 | marketing/CRM |
| tiny | 28 | ERP |
| vhsys | 54 | ERP |

**Total de tools MCP expostas: 1.358**

---

### 🟡 Skills SPECIAL (3)

#### evolution-api
- **Tipo:** Canal de mensageria (WhatsApp/Evolution)
- **Situação:** Não possui `mcp_server.py` Python. Integração feita via scripts shell em `scripts/`.
- **Ação:** Não aplicável ao critério PASS/FAIL desta auditoria. Verificação de canal separada recomendada.

#### telegram
- **Tipo:** Canal de mensageria
- **Situação:** Não possui `mcp_server.py` Python. Integração feita via scripts shell em `scripts/`.
- **Ação:** Não aplicável ao critério PASS/FAIL desta auditoria.

#### supabase
- **Tipo:** Banco de dados / infra
- **Situação:** Usa o pacote NPM `@supabase/mcp-server-supabase` (não é servidor Python). Opera como daemon de sincronização: lê lista de projetos via edge function do painel e registra uma entrada `supabase_<slug>` por projeto no `openclaw.json`, reiniciando o gateway se houver mudanças.
- **Variáveis necessárias:** `PANEL_BASE_URL`, `PANEL_TOKEN`, `HOOKS_TOKEN`
- **Ação:** Verificar via `npx @supabase/mcp-server-supabase --help` + teste de handshake Node.js separado.

---

## Diagnóstico de FAILs

**Nenhum FAIL detectado.** Todas as 16 skills Python:
- Passam na checagem de sintaxe (`ast.parse`)
- Iniciam o processo sem crash de import
- Respondem ao handshake `initialize` (protocolo `2024-11-05`)
- Listam suas tools via `tools/list`
- Retornam erro controlado (JSON-RPC error ou `isError: true`) ao chamar uma tool com credenciais dummy

---

## Fixes Aplicados

**Nenhum fix necessário.** Zero bugs de boot ou import encontrados.

---

## Ambiente de Teste

```
Python:    3.12 (.venv/bin/python3)
mcp:       1.27.1
httpx:     0.28.1
pydantic:  2.13.4
anyio:     4.13.0
Timeout:   10s por operação (boot: 1s + cada handshake: até 10s)
Env vars:  dummy (ex: OMIE_APP_KEY=dummy, ASAAS_API_KEY=dummy, etc.)
Repo:      /Users/barboza/agente-cfo (dev local)
Data:      2026-05-20
```

---

## Próximos Passos Recomendados

1. **evolution-api / telegram:** Implementar `mcp_server.py` ou documentar que são canais sem MCP próprio.
2. **supabase:** Criar teste de handshake Node.js equivalente para o npm package.
3. **Deploy:** Este audit foi no repo de dev local. Replicar no ambiente VPS de produção com credenciais reais para validar autenticação end-to-end.
4. **CI:** Integrar `mcp_audit.py` no pipeline de testes para detectar regressões de boot.
