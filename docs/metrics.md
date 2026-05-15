# Métricas e Observability — Agente CFO

## Sprint 40 — cliente vê o que Marcos faz, sem SSH

---

## Arquitetura

```
Daemons (cfo-*) → metric_emit.sh → metrics.jsonl
Marcos (tool calls) → metric_emit.sh → metrics.jsonl
                                               ↓
                            metrics_publisher.py (60s loop)
                                               ↓
                            POST /metrics-publish (painel)
                                               ↓
                            instance_metrics (Supabase)
                                               ↓
                            painel /settings/observability
```

---

## metrics.jsonl (local)

Arquivo: `~/.agente-cfo/logs/metrics.jsonl`

Formato de cada linha:
```json
{
  "ts": "2026-05-15T12:00:00Z",
  "daemon": "cfo-credentials-sync",
  "cycle_ms": 1234,
  "errors": 0,
  "meta": { "skills_updated": 3 }
}
```

Emitido por:
- Cada daemon CFO no fim de cada ciclo
- `metric_emit.sh` quando Marcos usa uma ferramenta
- `mcp_warmer.py` após cada warm cycle

---

## metric_emit.sh

```bash
bash metric_emit.sh <metric_name> <value_ms> [meta_json]
```

**Uso por Marcos:**
```bash
# Após consultar HubSpot
bash "$HOME/.openclaw/workspace/skills/agente-cfo/scripts/metric_emit.sh" \
  "hubspot.list_deals" 1234 '{"deals_returned":23}'

# Após executar automação
bash "$HOME/.openclaw/workspace/skills/agente-cfo/scripts/metric_emit.sh" \
  "automation.run" 12500 '{"automation":"relatorio_semanal","status":"success"}'
```

Validação: metric_name aceita apenas `[a-zA-Z0-9._:-]+`.

---

## Métricas coletadas

### Por daemon (agregadas das últimas 24h)

| Métrica | Descrição |
|---------|-----------|
| `daemon.cycle_count` | Total de ciclos executados |
| `daemon.error_count` | Total de erros nos ciclos |
| `daemon.avg_cycle_ms` | Tempo médio por ciclo |
| `daemon.error_rate` | Taxa de erro (erros/ciclos) |
| `daemon.active` | 1=ativo, 0=parado, -1=desconhecido |

### Por tool (emitidas via metric_emit.sh)

| Métrica | Descrição |
|---------|-----------|
| `tool.call_count` | Total de chamadas nas 24h |
| `tool.avg_ms` | Tempo médio de resposta |

### OpenClaw usage

| Métrica | Descrição |
|---------|-----------|
| `openclaw.total_tokens_today` | Tokens totais consumidos hoje |
| `openclaw.cost_usd_today` | Custo estimado em USD hoje |

### MCP Warmer

| Métrica | Descrição |
|---------|-----------|
| `mcp.warmup_ms` | Tempo de warm por MCP server |

---

## Schema Supabase

Migration a aplicar no Supabase Dashboard ou via CLI:

```sql
CREATE TABLE IF NOT EXISTS instance_metrics (
  id bigserial PRIMARY KEY,
  metric_name text NOT NULL,
  metric_value numeric NOT NULL,
  labels jsonb DEFAULT '{}'::jsonb,
  recorded_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_instance_metrics_name_time
  ON instance_metrics(metric_name, recorded_at DESC);

-- RLS: service_role pode tudo, authenticated pode ler
ALTER TABLE instance_metrics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON instance_metrics
  FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "auth_select" ON instance_metrics
  FOR SELECT TO authenticated USING (true);
```

---

## Edge function necessária (Lovable AI)

`POST /metrics-publish` (verify_jwt=false, auth via X-Panel-Token + X-Hooks-Token):

```typescript
// Body: Array<{ metric_name, metric_value, labels, recorded_at }>
// Action: INSERT em instance_metrics em batch
// Retorna: { inserted: N }
```

---

## Logs locais

| Arquivo | Conteúdo |
|---------|---------|
| `~/.agente-cfo/logs/metrics.jsonl` | Registros brutos de cada ciclo/tool |
| `~/.agente-cfo/logs/metrics-publisher.log` | Logs do publisher |

```bash
# Ver últimas métricas emitidas
tail -20 ~/.agente-cfo/logs/metrics.jsonl | python3 -m json.tool

# Ver status do publisher
journalctl -u cfo-metrics-publisher -n 20
```
