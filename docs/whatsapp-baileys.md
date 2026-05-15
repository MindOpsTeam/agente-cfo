# WhatsApp — Baileys (nativo) vs Evolution API

## Sprint 51 — WhatsApp Baileys via OpenClaw

OpenClaw tem um plugin nativo `@openclaw/whatsapp` que usa a mesma lib Baileys
da Evolution API. Mais simples de operar — zero Docker, zero setup extra.

---

## Comparação

| Aspecto | Baileys Nativo (@openclaw/whatsapp) | Evolution API (skill legada) |
|---------|-------------------------------------|------------------------------|
| Setup | `openclaw plugins install @openclaw/whatsapp` | Docker ou VPS dedicada |
| Instâncias | 1 conta principal | Multi-instância simultânea |
| QR Code | Gerado pelo `openclaw channels login` | Via painel Evolution |
| Manutenção | Zero — OpenClaw gerencia sessão | cfo-evolution-sync daemon |
| Multi-number | Não (1 por gateway) | Sim |
| Recomendado para | 1 empresa / 1 número | Múltiplos números simultâneos |

**Recomendação**: use Baileys nativo para o caso padrão. Use Evolution se precisar
de múltiplos números WhatsApp ao mesmo tempo.

---

## Baileys nativo — Setup

### 1. Plugin instalado automaticamente no setup.sh

O `install/setup.sh` (Sprint 51) instala automaticamente:
```bash
openclaw plugins install @openclaw/whatsapp
```

### 2. Parear via admin_action (sem SSH)

Via painel ou Marcos:
```bash
# Inicia o processo de pareamento
echo '{"action":"whatsapp_pair_start"}' | bash admin_action.sh

# Verifica status (polling enquanto aguarda QR)
echo '{"action":"whatsapp_pair_status"}' | bash admin_action.sh

# Quando status=qr_ready, busca o QR ASCII art
echo '{"action":"whatsapp_pair_qr"}' | bash admin_action.sh

# Cancela se necessário
echo '{"action":"whatsapp_pair_cancel"}' | bash admin_action.sh
```

### 3. Fluxo de pareamento

```
whatsapp_pair_start
  ↓
openclaw channels login --channel whatsapp (background)
  ↓
stdout capturado → QR ASCII art detectado
  ↓
state: qr_ready + qr_ascii salvo em /tmp/cfo-whatsapp-pair.json
  ↓
whatsapp_pair_qr → retorna ASCII art para o painel renderizar
  ↓
Usuário escaneia QR no celular (WhatsApp → Aparelhos vinculados)
  ↓
state: connected → sessão persistida pelo OpenClaw Gateway
```

### 4. Status possíveis

| Status | Descrição |
|--------|-----------|
| `idle` | Nenhum pareamento em andamento |
| `starting` | Processo iniciado, aguardando QR |
| `qr_ready` | QR disponível para escaneamento |
| `connected` | WhatsApp pareado com sucesso |
| `failed` | Erro no pareamento (QR expirou, sessão logada, etc.) |
| `cancelled` | Processo cancelado manualmente |

### 5. Admin actions disponíveis

| Action | Descrição |
|--------|-----------|
| `whatsapp_pair_start` | Inicia pareamento (spawna login em background) |
| `whatsapp_pair_status` | Retorna state JSON atual |
| `whatsapp_pair_qr` | Retorna QR ASCII art (status=qr_ready) |
| `whatsapp_pair_cancel` | Cancela processo em andamento |
| `whatsapp_status` | Status do canal WA no gateway OpenClaw |
| `whatsapp_send` | Envia mensagem `{chat_id, text}` |

---

## Evolution API — Quando usar

Mantenha a skill `skills/evolution-api/` e `cfo-evolution-sync.service` se:
- Precisa de **múltiplos números** WhatsApp simultâneos (ex: `vendas`, `suporte`)
- Já tem Evolution API auto-hospedada rodando
- Quer webhook separado do gateway OpenClaw

Para adicionar via painel: Configurações → WhatsApp → Evolution API (legacy).

---

## Troubleshooting Baileys

| Problema | Solução |
|---------|---------|
| QR não aparece em 15s | `echo '{"action":"whatsapp_pair_cancel"}' \| bash admin_action.sh` e tenta de novo |
| "Session logged out" | Normal — QR expirou. Roda `whatsapp_pair_start` novamente |
| Mensagens não chegam | `echo '{"action":"whatsapp_status"}' \| bash admin_action.sh` — verifica estado |
| Gateway desconecta WA | `systemctl restart openclaw-gateway` — sessão restaura automaticamente |
