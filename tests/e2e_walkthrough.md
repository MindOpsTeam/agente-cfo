# E2E Walkthrough — Happy Path Completo

Teste manual do fluxo completo do Agente CFO, do zero ao funcionando.
Execute cada passo e confirme o resultado esperado antes de avançar.

---

## Pré-requisitos

- [ ] VPS Ubuntu 22.04+ com acesso root/sudo
- [ ] Conta Anthropic com API key
- [ ] Conta no painel (criar em https://carteira-do-agente.lovable.app)
- [ ] ERP com API (Asaas recomendado para este walkthrough — sandbox disponível)

---

## Passo 1 — Signup no painel

**Ação**: Acesse o painel e crie conta com e-mail.

**Resultado esperado**: Dashboard inicial sem erros. Seção "VPS" mostra "Offline".

---

## Passo 2 — Setup.sh na VPS

**Ação**: Cole o comando na VPS:
```bash
curl -fsSL https://raw.githubusercontent.com/MindOpsTeam/agente-cfo/main/install/setup.sh | bash
```

**Segue o wizard**: ERP = Asaas (API key de sandbox), sem CRM, sem cobrança adicional.

**Resultado esperado**:
```
✅ OpenClaw instalado
✅ Tunnel ativo: https://xxx.trycloudflare.com
✅ Instância registrada no painel
✅ Smoke test: integrations OK
Agente CFO instalado e operacional. Boas vendas! 💼
```

**Verifica no painel**: VPS vira "Online" com heartbeat fresco.

---

## Passo 3 — Adiciona Asaas em /integrations

**Ação**:
1. Painel → Configurações → Integrações → Asaas
2. Cola a API key (sandbox: `$aas_sandbox_key`)
3. Clica "Salvar e testar"

**Resultado esperado**: ícone verde "Conectado". API key salva encriptada.

**Aguarda ~3 minutos**: o `cfo-credentials-sync` materializa `~/.openclaw/secrets/asaas.env` na VPS.

**Verifica na VPS**:
```bash
cat ~/.openclaw/secrets/asaas.env
# deve mostrar ASAAS_API_KEY=<key>
```

---

## Passo 4 — MCP registrado automaticamente

**Ação**: aguarda o daemon registrar o MCP.

**Verifica** (painel ou VPS):
```bash
openclaw mcp list
# deve mostrar "asaas" na lista
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/integration_smoke.sh asaas
```

**Resultado esperado**:
```
✓ secrets present: ~/.openclaw/secrets/asaas.env
✓ mcp registered: python3 .../asaas/mcp_server.py
✓ mcp responds: 33 tools
✓ gateway: active
RESULT: ✅ PASS
```

---

## Passo 5 — Chat: "Marcos, qual saldo Asaas?"

**Ação**: Painel → /chat → digita "Marcos, qual o saldo disponível no Asaas?"

**Resultado esperado** (~5–15s):
```
Consultei o Asaas agora. Saldo disponível: R$ 0,00 (conta sandbox).
Se quiser sacar ou verificar cobranças, é só pedir.
```

> Saldo zero é esperado em sandbox.

**Verifica nos logs**:
```bash
# Na VPS
tail -10 ~/.agente-cfo/logs/credentials-sync.log
```

---

## Passo 6 — Configura Telegram

**Ação**:
1. Telegram → @BotFather → `/newbot` → copia token
2. Painel → Configurações → Telegram → "Adicionar bot" → cola token
3. Aguarda ~30s

**Verifica**:
```bash
journalctl -u cfo-telegram-sync -n 10 --no-pager
# deve mostrar "webhook registrado"
```

**Resultado esperado**: status "active" no painel.

---

## Passo 7 — Mensagem no Telegram

**Ação**: abra o bot no Telegram e mande "qual meu saldo no Asaas?"

**Resultado esperado** (~10–20s): Marcos responde diretamente no Telegram com o mesmo dado.

**Verifica no painel** → /chat: deve aparecer a conversa com `channel=telegram:<bot>`.

---

## Passo 8 — Configura alerta de custo

**Ação**: Painel → Alertas → "Novo alerta" → tipo "cost_budget" → threshold R$10 → canais ["panel", "telegram:marcoscfo_bot:SEU_CHAT_ID"]

**Resultado esperado**: alerta salvo. Próximo ciclo do `cfo-alerts-checker` avalia (60s).

**Para simular disparo** (forçar custo > R$10 é difícil em sandbox — só verifica que alerta foi criado):
```bash
journalctl -u cfo-alerts-checker -n 20 --no-pager
# deve mostrar "[check] 1 alertas avaliados"
```

---

## Passo 9 — Configura backup diário

**Ação**: Painel → Configurações → Backups → "Habilitar backup diário" (já configurado por padrão no setup).

**Verifica**:
```bash
ls -la ~/.agente-cfo/backups/
# deve mostrar backup criado durante o setup (às 03:00 via cron)
```

**Testa backup manual**:
```bash
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/backup_config.sh
# → ~/.agente-cfo/backups/cfo-backup-<timestamp>.tar.gz
```

---

## Passo 10 — Restore em outra VPS (simulação)

**Ação** (em VPS nova ou com `--dry-run` na mesma):

```bash
# Backup com secrets (para migração real)
bash backup_config.sh --include-secrets --output /tmp/cfo-migration.tar.gz

# Restore (dry-run para não afetar config atual)
bash restore_config.sh /tmp/cfo-migration.tar.gz --dry-run
```

**Resultado esperado**:
```
=== Restore CFO [DRY-RUN] ===
Backup: /tmp/cfo-migration.tar.gz
  Gerado em:    2026-05-15T...
  Inclui secrets: True
[DRY-RUN] Aplicaria: openclaw.json do backup
=== [DRY-RUN] 1 mudança(s) seriam aplicadas ===
```

---

## Passo 11 — Smoke test final

**Ação**:
```bash
bash ~/.openclaw/workspace/skills/agente-cfo/../../../tests/run_all.sh --fast
```

**Resultado esperado**:
```
✅ Todos os testes passaram!
Total: 43 | Passou: 41 | Pulou: 2
```

---

## Checklist de validação final

- [ ] VPS online no painel
- [ ] Asaas integrado (MCP ativo)
- [ ] Chat web respondendo
- [ ] Telegram bot ativo
- [ ] Alerta configurado
- [ ] Backup gerado
- [ ] Smoke tests passando
- [ ] Nenhum daemon em estado `failed`

---

## Tempos esperados

| Etapa | Duração |
|-------|---------|
| Setup.sh completo | ~5–10 min |
| Credenciais materializadas | ~3 min |
| MCP registrado | ~3 min |
| Primeira resposta do Marcos | ~5–15s |
| Telegram configurado | ~30s |

---

## Troubleshooting rápido

Ver [docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) para casos específicos.
