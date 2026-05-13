---
name: evolution-api
description: >
  Integração com Evolution API (open-source WhatsApp multi-instance).
  O daemon evolution_sync.py reconcilia instâncias do painel com a Evolution
  real, sincroniza status/QR codes, e garante que cada instância configurada
  exista na Evolution com o webhook correto apontando para o painel.
category: messaging
---

# Evolution API — Skill

## O que faz

- **Daemon `evolution_sync.py`**: loop a cada 30s, reconcilia estado do painel
  com a Evolution API real (cria instâncias, atualiza status, busca QR codes)
- **`evolution_client.py`**: wrapper Python de baixo nível para a Evolution API
- **`send_evolution.sh`**: helper shell que Marcos usa pra enviar mensagens
  (multi-instance — recebe `<instance>` como parâmetro)

## Auth

Usa as mesmas credenciais da VPS:
- `PANEL_BASE_URL`, `PANEL_TOKEN`, `HOOKS_TOKEN` (de `~/.agente-cfo/.env`)
- Config da Evolution (`base_url`, `api_key`) vem do painel via
  `GET /evolution-config-vps` — zero env vars extras na VPS

## Systemd

Serviço: `cfo-evolution-sync.service`

```bash
systemctl status cfo-evolution-sync
journalctl -u cfo-evolution-sync -f
```

## Enviar mensagem

```bash
bash ~/.openclaw/workspace/skills/evolution-api/scripts/send_evolution.sh \
  "minha-instancia" "+5511999999999" "Olá!"
```

## Logs

`~/.agente-cfo/logs/evolution-sync.log`
