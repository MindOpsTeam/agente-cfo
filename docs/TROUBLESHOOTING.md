# Troubleshooting — Agente CFO

Diagnóstico rápido dos problemas mais comuns.

---

## VPS offline / heartbeat parou

**Sintoma**: painel mostra "VPS offline" ou "Marcos indisponível".

**Diagnóstico**:
```bash
# Na VPS
systemctl status openclaw-gateway
systemctl status cloudflared-cfo
journalctl -u openclaw-gateway -n 20 --no-pager
```

**Soluções**:
```bash
# Gateway caiu
systemctl restart openclaw-gateway

# Tunnel Cloudflare caiu
systemctl restart cloudflared-cfo

# Config corrompida → auto-rollback
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/auto_rollback.sh

# Todos os serviços
systemctl restart openclaw-gateway cloudflared-cfo cfo-automation-engine
```

**Via painel** (se o tunnel ainda responde): Configurações → Sistema → "Reiniciar Gateway"

---

## Chat web não responde / Marcos demora demais

**Sintoma**: mensagem enviada, resposta nunca chega ou demora >120s.

**Diagnóstico**:
```bash
# Vê runs ativos
openclaw health

# Vê fila do agente
openclaw status | grep Queue

# Timeout? Vê logs
journalctl -u openclaw-gateway -n 50 --no-pager | grep -E "error|timeout|fail"
```

**Soluções**:
```bash
# Limpa fila travada
systemctl restart openclaw-gateway

# MCP server travado? Pre-warm forçado
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/mcp_sync_now.sh

# Verifica MCPs
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/integration_status.sh
```

---

## Integração ERP não funciona

**Sintoma**: "Não consegui acessar seu ERP" ou "credenciais inválidas".

**Diagnóstico**:
```bash
# Vê se credenciais foram materializadas
cat ~/.openclaw/secrets/omie.env
ls -la ~/.openclaw/secrets/

# Vê log do credentials-sync
journalctl -u cfo-credentials-sync -n 20 --no-pager
```

**Soluções**:
1. Painel → Configurações → Integrações → confirma que as credenciais estão salvas
2. Aguarda 3min (cfo-credentials-sync sincroniza a cada 3min)
3. Ou: `systemctl restart cfo-credentials-sync`
4. Testa smoke: `bash ~/.openclaw/workspace/skills/agente-cfo/scripts/integration_smoke.sh omie`

---

## WhatsApp QR não aparece / não conecta

**Sintoma**: painel mostra QR pendente mas não atualiza, ou status não vira "connected".

**Diagnóstico**:
```bash
journalctl -u cfo-evolution-sync -n 30 --no-pager
# Procura por "getMe OK" ou erros de API key
```

**Soluções**:
1. Verifica que Evolution API está online: `curl https://sua-evolution.com/instance/fetchInstances -H "apikey: SEU_KEY"`
2. Painel → Configurações → WhatsApp → "Forçar Sync"
3. Se QR expirou: no painel, clique em "Gerar novo QR"
4. `systemctl restart cfo-evolution-sync`

---

## Telegram bot não responde

**Sintoma**: mensagem enviada para o bot, sem resposta do Marcos.

**Diagnóstico**:
```bash
journalctl -u cfo-telegram-sync -n 20 --no-pager
# Procura por "webhook registrado" ou erros
```

**Soluções**:
1. Vê se bot token é válido: `curl https://api.telegram.org/botSEU_TOKEN/getMe`
2. `systemctl restart cfo-telegram-sync`
3. Painel → Configurações → Telegram → "Reconectar bot"

---

## MCP server timeout / tool call falhou

**Sintoma**: Marcos diz "não consegui acessar o HubSpot/Omie/etc".

**Diagnóstico**:
```bash
# Testa MCP específico
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/integration_smoke.sh hubspot

# Vê logs de warm
tail -50 ~/.agente-cfo/logs/mcp-warmer.log
```

**Soluções**:
```bash
# Força warm imediato
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/mcp_sync_now.sh

# Verifica credenciais do MCP
cat ~/.openclaw/secrets/hubspot.env

# Reinstala dependência Python (se mcp_server.py quebrou)
source /opt/agente-cfo/.venv/bin/activate
pip install --upgrade mcp
```

---

## Daemon CFO em loop de restart

**Sintoma**: `systemctl status cfo-*` mostra "activating (start)" repetidamente; `NRestarts` alto.

**Diagnóstico**:
```bash
journalctl -u cfo-automation-engine -n 50 --no-pager
systemctl show cfo-automation-engine --property=NRestarts,Result
```

**Soluções**:
```bash
# Vê o erro específico
journalctl -u cfo-automation-engine -p err -n 20 --no-pager

# Se é erro de config/script (temporário)
systemctl reset-failed cfo-automation-engine
systemctl start cfo-automation-engine

# Se é loop grave (>10 restarts/24h)
# health_doctor.py vai PARAR o service — este é o comportamento esperado
# Veja o log do health-doctor para entender o diagnóstico
tail -30 ~/.agente-cfo/logs/health-doctor.log
```

---

## Alertas não disparam

**Sintoma**: condição configurada está sendo atendida mas sem notificação.

**Diagnóstico**:
```bash
tail -30 ~/.agente-cfo/logs/alerts-checker.log
# Procura por "[check] ALERTA" ou "[check] em cooldown"
```

**Causas comuns**:
1. **Cooldown ativo** (padrão 30min): aguarda ou reduz `condition.cooldown_min` no painel
2. **Edge fn `alerts-config-vps-list` não deployada**: `[] alertas` no log → deploy pendente
3. **Canal de notificação mal configurado**: veja formato `whatsapp:instance:phone`
4. **Métricas não chegando**: verifica `~/.agente-cfo/logs/metrics.jsonl`

---

## Custo Anthropic alto inesperado

**Diagnóstico**:
```bash
python3 ~/.openclaw/workspace/skills/agente-cfo/scripts/cost_estimator.py
```

**Causas comuns**:
1. Automação em loop (faz muitas chamadas LLM)
2. Context muito grande (>500k tokens por sessão)
3. Heartbeat/proactive muito frequente

**Soluções**:
1. Painel → Alertas → configura `cost_budget` com threshold adequado
2. Aumenta intervalo do heartbeat: `openclaw config set agents.defaults.heartbeat.intervalMinutes 60`
3. Compacta contexto: Marcos pode ser instruído a fazer `/compactar` periodicamente

---

## "User already registered" no painel

**Sintoma**: tentativa de login ou signup dá esse erro.

**Solução**: use "Esqueci minha senha" na tela de login. Single-tenant: 1 conta por painel.

---

## openclaw.json corrompido → gateway não sobe

**Diagnóstico**:
```bash
openclaw config validate
# Se inválido:
```

**Solução automática** (health_doctor detecta e aplica):
```bash
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/auto_rollback.sh
systemctl restart openclaw-gateway
```

**Manual** (se o auto-rollback falhou):
```bash
ls -lt ~/.openclaw/openclaw.json.bak*
# Pega o mais recente que for válido:
OPENCLAW_CONFIG_PATH=~/.openclaw/openclaw.json.bak openclaw config validate
# Se OK:
cp ~/.openclaw/openclaw.json.bak ~/.openclaw/openclaw.json
systemctl restart openclaw-gateway
```

---

## Checklist de saúde rápida

```bash
# 1. Gateway up?
openclaw health

# 2. Todos os daemons OK?
for svc in openclaw-gateway cloudflared-cfo cfo-automation-engine cfo-credentials-sync \
           cfo-evolution-sync cfo-telegram-sync cfo-mcp-warmer cfo-metrics-publisher \
           cfo-alerts-checker cfo-health-doctor; do
    status=$(systemctl is-active $svc 2>/dev/null || echo unknown)
    echo "$svc: $status"
done

# 3. MCPs respondem?
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/integration_status.sh

# 4. Logs de erro recentes?
journalctl -p err --since "1 hour ago" --no-pager | grep cfo | tail -20

# 5. Custo do dia?
python3 ~/.openclaw/workspace/skills/agente-cfo/scripts/cost_estimator.py
```
