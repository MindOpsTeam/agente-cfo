# Arquitetura — Agente CFO

Visão técnica para quem quer entender o sistema, fazer um fork ou depurar problemas mais profundos.

---

## Stack

| Camada | Tecnologia | Onde roda |
|---|---|---|
| **Agente de IA** | OpenClaw + Claude (Anthropic) | VPS do cliente |
| **Skills** | Python 3 + Bash | VPS do cliente |
| **WhatsApp** | wacli (WhatsApp Web protocol) | VPS do cliente |
| **Tunnel de entrada** | Cloudflare Tunnel | VPS do cliente → Cloudflare |
| **Banco de dados** | Supabase (PostgreSQL) | Supabase do cliente |
| **Edge functions** | Deno/TypeScript no Supabase | Supabase do cliente |
| **Painel web** | Lovable Cloud (React) | Lovable Cloud |

---

## Diagrama de Fluxo

### Alertas proativos (saída)

```
Cron (OpenClaw)                   VPS do cliente
        │
        ▼  07:00 / 18:00
┌───────────────────┐
│  alerta_manha.md  │  ← prompt template
│  alerta_tarde.md  │
└────────┬──────────┘
         │ erp_gateway.py get_balance
         │ erp_gateway.py list_receivables
         │ erp_gateway.py list_payables
         │ crm_gateway.py get_pipeline_projection
         ▼
┌───────────────────┐
│   ERP / CRM API   │  ← Omie, Bling, HubSpot etc.
└────────┬──────────┘
         │ dados financeiros normalizados
         ▼
┌───────────────────┐
│   Claude (LLM)    │  ← formata mensagem WhatsApp
└────────┬──────────┘
         │ mensagem em texto plano
         ▼
┌───────────────────┐
│  _send_whatsapp.sh│  ← wacli send
└────────┬──────────┘
         │ WhatsApp
         ▼
    📱 Dono da empresa
```

### Conversa inbound (entrada)

```
    📱 Dono da empresa
         │ WhatsApp
         ▼
┌───────────────────┐
│ wacli-inbound.py  │  ← daemon escutando mensagens
└────────┬──────────┘
         │ POST /hooks/agent
         ▼
┌───────────────────┐
│  OpenClaw gateway │  ← processa com conversa.md
└────────┬──────────┘
         │ identifica intent
         ▼
┌───────────────────┐
│ erp_gateway.py /  │  ← coleta dados via API
│ crm_gateway.py    │
└────────┬──────────┘
         │ dados
         ▼
┌───────────────────┐
│   Claude (LLM)    │  ← formata resposta
└────────┬──────────┘
         │ _send_whatsapp.sh
         ▼
    📱 Dono da empresa
```

### Detecção de anomalias (daemon proativo)

```
cfo_proactive_watcher.py          VPS do cliente
  ┌─────────────────────────────────────────┐
  │  Loop a cada 30 min                      │
  │                                          │
  │  Para cada regra em proactive_rules/:    │
  │    rule.evaluate(erp_client, crm_client) │
  │         │                                │
  │    Alerta?  ──Não──▶ (próxima regra)     │
  │         │ Sim                            │
  │    Em cooldown? ──Sim──▶ (ignora)        │
  │         │ Não                            │
  │    POST /hooks/agent (dispatch_alert)    │
  │    → OpenClaw processa proactive.md     │
  │    → wacli envia alerta WhatsApp         │
  │    POST /event (painel Supabase)         │
  └─────────────────────────────────────────┘
```

### Comando remoto do painel (entrada via tunnel)

```
Painel Lovable         Supabase Edge Functions
     │                          │
     │  clicar "push command"   │
     ▼                          ▼
┌──────────┐         ┌────────────────────┐
│  Browser │──POST──▶│  push-command/     │
└──────────┘         │  (Deno function)   │
                     └────────┬───────────┘
                              │ HTTP POST
                              ▼
                     ingress_url (Cloudflare Tunnel)
                              │
                              ▼
                     ┌────────────────────┐
                     │  OpenClaw gateway  │  VPS
                     │  porta 18789       │
                     └────────────────────┘
```

---

## Onde mora cada peça

### Na VPS do cliente (`~/.agente-cfo/` e `~/.openclaw/`)

```
~/.agente-cfo/
├── .env                        # Variáveis de ambiente (API keys, tokens)
├── instance.env                # INSTANCE_ID, INGRESS_URL
├── cron-ids.env                # IDs dos cron jobs registrados
├── memory/                     # Histórico de conversas por JID
│   └── threads/
├── state/
│   └── proactive_alerts.json   # Estado de cooldown das regras proativas
└── logs/
    └── proactive.log           # Log do daemon de detecção

~/.openclaw/
├── workspace/
│   └── skills/
│       ├── _lib/               # base.py (BaseERPClient, BaseCRMClient)
│       ├── agente-cfo/         # Skill principal (prompts, scripts)
│       ├── omie/               # Skills de ERP/CRM
│       ├── bling/
│       └── ...
└── secrets/
    ├── omie.env                # Credenciais por skill (chmod 600)
    ├── bling.env
    └── ...
```

### No Supabase do cliente

```
Banco PostgreSQL:
  instances     ← VPS registradas (hostname, versão, ingress_url)
  events        ← Log de alertas, envios, erros
  configs       ← Configurações do painel (thresholds, rules on/off)

Edge Functions (Deno):
  instance-register   ← VPS chama ao subir (registra/atualiza)
  heartbeat           ← VPS chama periodicamente (keep-alive)
  event               ← VPS envia eventos (alertas, erros)
  llm-usage           ← VPS reporta custo Anthropic
  push-command        ← Painel envia comandos para a VPS
```

---

## Como o BaseERPClient / BaseCRMClient funciona

Toda integração com ERP ou CRM herda de uma classe base em `skills/_lib/base.py`.

### BaseERPClient

```python
class BaseERPClient(ABC):
    SKILL_NAME: str = ""          # ex: "omie", "bling"

    @abstractmethod
    def get_balance(self) -> dict:
        # Retorna: {"balance_brl": float, "as_of": ISO8601}
        ...

    @abstractmethod
    def list_payables(self, from_date, to_date, limit, page) -> dict:
        # Retorna: make_list_response([make_payable_item(...)])
        ...

    @abstractmethod
    def list_receivables(self, from_date, to_date, limit, page) -> dict:
        # Retorna: make_list_response([make_receivable_item(...)])
        ...

    # Implementações padrão (não precisam de override):
    def list_overdue(self) -> dict: ...          # filtra pending < hoje
    def get_cash_projection(self, days) -> dict: ... # 30/90d breakdown semanal

    # Write ops (optional — retornam NotImplementedError se não implementadas):
    def pay_payable(self, id): ...
    def mark_received(self, id): ...
    def create_payable(self, amount, due_date, supplier, **kwargs): ...
    def create_receivable(self, amount, due_date, customer, **kwargs): ...
    def cancel_payable(self, id): ...

    def run_cli(self) -> None: ...  # parse sys.argv e despacha para o método correto
```

### BaseCRMClient

```python
class BaseCRMClient(ABC):
    @abstractmethod
    def list_deals(self, status, limit, page) -> dict:
        # Retorna: make_list_response([make_deal_item(...)])
        ...

    # Implementações padrão:
    def pipeline_summary(self) -> dict: ...           # agrega por stage
    def get_pipeline_projection(self, horizon_days) -> dict: ... # breakdown semanal

    # Write ops (optional):
    def move_deal(self, id, to_stage): ...
    def update_deal(self, id, amount, close_date): ...
    def create_deal(self, title, amount, pipeline): ...
    def add_deal_note(self, id, note): ...
    def mark_deal_won(self, id): ...
    def mark_deal_lost(self, id, reason): ...
```

### Schema normalizado de retorno

Todas as skills retornam os mesmos campos — o agente não precisa conhecer os detalhes de cada API:

```python
# Conta a pagar/receber
{
    "id": str,
    "due_date": "YYYY-MM-DD",
    "amount_brl": float,
    "counterparty": str,        # nome do fornecedor ou cliente
    "status": "pending|paid|received|overdue",
    "category": str | None,
    "raw": dict,                # resposta original da API (para debug)
}

# Deal de CRM
{
    "id": str,
    "title": str,
    "amount_brl": float | None,
    "stage": str,               # label do stage (não ID interno)
    "status": "open|won|lost",
    "expected_close_date": "YYYY-MM-DD" | None,
    "owner": str | None,
    "raw": dict,
}
```

---

## Regras proativas (cfo_proactive_watcher.py)

O daemon avalia 8 regras a cada 30 minutos. Cada regra:

1. Recebe `erp_client` e `crm_client` já instanciados
2. Retorna uma lista de `Alert(rule_name, severity, summary, raw_data, dedup_key)`
3. Tem um `cooldown_hours` — o mesmo `dedup_key` não dispara dentro do cooldown

O estado de cooldown é persistido em `~/.agente-cfo/state/proactive_alerts.json`.

Para criar uma nova regra, basta criar `skills/agente-cfo/scripts/proactive_rules/rule_minha_regra.py` herdando `ProactiveRule` e adicionar ao `RULE_MODULES` em `cfo_proactive_watcher.py`.

---

## Gateways (erp_gateway.py / crm_gateway.py)

Os gateways são scripts de entrada genéricos. Leem `CFO_ERP_NAME` (ou `CFO_CRM_NAME`) do `.env`, instanciam o client da skill correspondente e despacham o comando:

```bash
# Em vez de chamar o client diretamente:
python3 ~/.openclaw/workspace/skills/omie/scripts/omie_client.py get_balance

# Os prompts usam o gateway, que é agnóstico ao ERP:
python3 $SCRIPTS_DIR/erp_gateway.py get_balance
```

Isso permite que os prompts (`alerta_manha.md`, `conversa.md` etc.) funcionem com qualquer ERP sem modificação.

---

## Services systemd

| Service | Descrição | Restart |
|---|---|---|
| `openclaw-gateway` | Agente principal OpenClaw | always |
| `wacli-inbound` | Escuta mensagens WhatsApp | always |
| `cfo-proactive` | Daemon de detecção de anomalias | always |
| `cloudflared` | Tunnel para receber comandos do painel | always |

```bash
# Ver todos os services do Agente CFO
systemctl list-units | grep -E "openclaw|wacli|cfo-proactive|cloudflared"

# Reiniciar tudo
systemctl restart openclaw-gateway wacli-inbound cfo-proactive cloudflared
```
