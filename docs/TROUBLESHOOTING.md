# Troubleshooting — Agente CFO (Marcos)

> Soluções para os problemas mais comuns. Se não resolver, abra uma issue no GitHub.

---

## Diagnóstico rápido

```bash
# Na VPS: roda o doctor completo
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/doctor.sh

# Ou via painel: Configurações → Sistema → "Executar diagnóstico"
```

O doctor verifica todos os componentes e indica o que está com problema.

---

## Marcos não responde

### 1. Gateway OpenClaw offline

```bash
# Verificar status
systemctl status openclaw-gateway

# Se parado:
systemctl start openclaw-gateway

# Ver logs de erro:
journalctl -u openclaw-gateway -n 50
```

**Causa comum:** VPS sem memória. Verifique: `free -m`  
**Solução:** reiniciar VPS ou aumentar swap: `fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`

### 2. Heartbeat parado (painel mostra VPS offline)

```bash
# Ver último heartbeat
systemctl status openclaw-gateway | grep "Active"

# Verificar conectividade do tunnel
systemctl status cloudflared-cfo
journalctl -u cloudflared-cfo -n 20
```

**Causa comum:** URL do Cloudflare Tunnel mudou após restart.  
**Solução:**
```bash
# Reiniciar tunnel e atualizar URL
systemctl restart cloudflared-cfo
sleep 10
journalctl -u cloudflared-cfo -n 30 | grep "trycloudflare.com"
# Copiar nova URL e atualizar no painel: Configurações → Sistema → "Atualizar URL da VPS"
```

### 3. Tools = 0 no trajectory

Marcos está respondendo mas sem usar ferramentas. Provavelmente `tools.profile` não está configurado.

```bash
openclaw config get tools.profile
# Deve retornar "coding"

# Se não retornar:
openclaw config set tools.profile coding
systemctl restart openclaw-gateway
```

---

## WhatsApp

### QR code não aparece / não pareia

```bash
# Ver status da conexão
wacli doctor

# Se "NOT LINKED":
wacli logout 2>/dev/null; true
# Abrir painel → Configurações → WhatsApp → "Novo pareamento" → escanear QR
```

### WhatsApp desconecta frequentemente

```bash
# Verificar daemon de sync
systemctl status wacli-sync
journalctl -u wacli-sync -n 30

# Reiniciar
systemctl restart wacli-sync
```

**Causa comum:** número sem atividade por muito tempo. Use o mesmo número normalmente.

### "no LID found" ao enviar

```bash
# Bug do wacli com números BR de 13 dígitos
# Usar JID direto em vez de número E.164
# O Marcos já trata isso automaticamente desde wacli 0.7.x
wacli --version  # Deve ser 0.7.0+
```

### Evolution API não recebe webhooks

```bash
# Verificar instância ativa
curl http://localhost:8080/instance/fetchInstances \
  -H "apikey: $EVOLUTION_API_KEY" | python3 -m json.tool

# Recriar webhook se necessário
# Ver painel → Configurações → Sistema → "Reconfigurar Evolution API"
```

---

## ERP e integrações

### ERP retorna 401 (token inválido)

Marcos vai responder automaticamente com:
> "Credencial [ERP] inválida. Atualize em [painel]/integrations/[erp]"

**Como resolver:**
1. Painel → Integrações → card do ERP → "Editar"
2. Atualize a API key
3. Clique em "Testar" — deve ficar verde
4. Aguarde ~3 minutos para o `credentials-sync` atualizar na VPS

### Omie retorna 404 em create_payable

**Causa:** plano Omie modo teste sem módulo financeiro.

O Marcos já trata isso com fallback: o lançamento fica no painel (`dashboard_only`) e você pode migrar para o Omie depois quando o plano for ativado.

### HubSpot retorna MISSING_SCOPES

```
O token HubSpot não tem permissão para criar Deals.
```

**Como resolver:**
1. Acesse [app.hubspot.com](https://app.hubspot.com) → Settings → Integrations → Private Apps
2. Edite o app → Scopes → adicione `crm.objects.deals.write`
3. Gere novo token e atualize no painel

### credentials-sync não funciona

```bash
# Ver logs do sync
tail -50 ~/.agente-cfo/logs/credentials-sync.log

# Forçar sync manual
python3 ~/.openclaw/workspace/skills/agente-cfo/scripts/credentials_sync.py

# Verificar se PANEL_TOKEN está OK
echo $PANEL_TOKEN | head -c 10
```

---

## Daemons systemd

### Verificar todos os daemons CFO

```bash
for svc in openclaw-gateway wacli-inbound wacli-sync cfo-proactive \
           cfo-credentials-sync cfo-supabase-sync cfo-metrics-publisher \
           cfo-alerts-checker cfo-health-doctor cloudflared-cfo; do
    status=$(systemctl is-active "$svc" 2>/dev/null || echo "missing")
    echo "$status | $svc"
done
```

### Daemon reiniciando em loop

```bash
# Ver quantas vezes reiniciou
journalctl -u NOME_DO_DAEMON --since "1 hour ago" | grep "Started\|Failed"

# Se >5 restarts: ver log completo
journalctl -u NOME_DO_DAEMON -n 100
```

**Causas comuns:**
- `cfo-proactive`: ERP sem credencial configurada → configure no painel
- `cfo-supabase-sync`: PANEL_BASE_URL ou PANEL_TOKEN inválidos → verificar `.env`
- `wacli-inbound`: WhatsApp desconectado → reconectar

### Reiniciar todos de uma vez

```bash
systemctl restart \
  openclaw-gateway \
  wacli-inbound wacli-sync \
  cfo-proactive cfo-credentials-sync \
  cfo-supabase-sync cfo-metrics-publisher \
  cfo-health-doctor
```

---

## Tunnel Cloudflare

### URL do tunnel muda a cada restart

Cloudflare Quick Tunnels geram URL nova a cada inicialização. Isso é esperado.

**Solução permanente:** configure um túnel nomeado com seu próprio domínio:
```bash
cloudflared tunnel create marcos-tunnel
cloudflared tunnel route dns marcos-tunnel marcos.seudominio.com
# Atualizar config em /etc/systemd/system/cloudflared-cfo.service
```

### Tunnel não sobe

```bash
# Verificar conectividade com Cloudflare
curl -I https://cloudflare.com

# Ver erro específico
journalctl -u cloudflared-cfo -n 30

# Reiniciar
systemctl restart cloudflared-cfo
```

---

## Painel e Supabase

### Edge functions retornam 401

**Causa:** usuário não autenticado ou token expirado.

Faça logout e login novamente no painel. Se persistir, verifique se o JWT do Supabase não está expirado.

### Painel mostra "VPS offline" mas VPS está UP

```bash
# Verificar se heartbeat está sendo enviado
tail -20 ~/.agente-cfo/logs/heartbeat.log

# Testar manualmente
curl -X POST "$PANEL_BASE_URL/heartbeat" \
  -H "Content-Type: application/json" \
  -H "X-Panel-Token: $PANEL_TOKEN" \
  -d "{\"instance_id\":\"$INSTANCE_ID\"}"
```

### Chat messages ficam em "pending"

Isso acontece quando `panel_post_reply.sh` não encontra `thread_id`/`run_id`. O auto-discover via `chat-pending-lookup` deve resolver.

Se persistir: verifique se a edge fn `chat-pending-lookup` existe no Supabase:
```bash
curl "$PANEL_BASE_URL/chat-pending-lookup?channel=panel&external_id=teste" \
  -H "X-Panel-Token: $PANEL_TOKEN"
```

---

## Performance

### Respostas lentas (>30s)

1. **Checar memória:** `free -m` — se < 200 MB livre, adicionar swap
2. **Checar carga:** `top` ou `htop`
3. **MCP cold-start:** primeiras chamadas ao MCP são lentas. O warmer resolve:
   ```bash
   systemctl status cfo-mcp-warmer
   ```
4. **Anthropic lento:** pode ser instabilidade na API. Ver [status.anthropic.com](https://status.anthropic.com)

---

## Reinstalar do zero

```bash
# Na VPS: backup primeiro
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/backup_config.sh

# Desinstalar (mantém CLI)
openclaw uninstall

# Reinstalar via painel → Configurações → Sistema → "Gerar novo comando de instalação"
```
