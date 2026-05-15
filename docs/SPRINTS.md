# Histórico de Sprints — Agente CFO

Cada sprint = 1 feature ou conjunto de features relacionadas.
Ordem cronológica reversa (mais recente primeiro).

---

| Sprint | Entrega |
|--------|---------|
| **47** | Documentação final consolidada (README, CLIENTE, ARCHITECTURE, SPRINTS, TROUBLESHOOTING) |
| **46** | `memory_export.sh` + `memory_import.sh` + `memory_stats.sh` — portabilidade da memória do Marcos |
| **45** | `backup_config.sh` + `restore_config.sh` + cron diário às 03h — backup/restore de configuração |
| **44** | `health_doctor.py` + `auto_rollback.sh` — auto-recovery de daemons + cooldown inteligente systemd |
| **42** | `alerts_checker.py` + `cost_estimator.py` — alertas configuráveis (error_rate, daemon_down, cost_budget, latency) |
| **40** | `metrics_publisher.py` + `metric_emit.sh` + migration `instance_metrics` — observabilidade |
| **37** | `admin_action.sh` — 21 ações administrativas whitelisted via painel/Marcos (zero SSH) |
| **36** | `mcp_warmer.py` — pre-warm de MCP servers + npm global install (redução de cold-start) |
| **35** | `incoming-message` edge fn + pipeline cross-channel unificado + `panel_post_reply.sh` |
| **34** | Skill `telegram` — `telegram_client.py` + `telegram_sync.py` + `send_telegram.sh` + systemd |
| **33** | `chat_messages.channel` migration + `whatsapp-incoming-webhook` refatorado (pipeline unificado) |
| **31** | Investigação protocolo WebSocket OpenClaw + `ws_chat_example.html` + `docs/openclaw-ws.md` |
| **30** | HubSpot dual-auth: Private App Token + OAuth 2.0 com auto-refresh em 401 |
| **29** | `integration_smoke.sh` + `integration_status.sh` — smoke test E2E plug-and-play |
| **28** | Fix `supabase_sync`: `mcp.servers` (caminho canônico) + `mcp_manager.py` + plug-and-play unificado |
| **27** | Skill `evolution-api` — `evolution_client.py` + `evolution_sync.py` + `send_evolution.sh` + systemd |
| **26** | `credentials_sync.py` daemon + `self_update.sh` — zero SSH para credenciais e updates |
| **25** | Skill `supabase` — `supabase_sync.py` orquestra `@supabase/mcp-server-supabase` por projeto |
| **24** | HubSpot 267→463 tools: CMS, Files, Conversations, Marketing, Settings, Automation, KB |
| **23** | Sprint de gaps: Kommo 55→85, Omie 87→96, Bling 101→116, Pipedrive 127→144, HubSpot 133→267 |
| **22** | Kommo do zero (55 tools), Omie 41→87, Bling 35→101, Pipedrive 35→127, HubSpot 38→133 |
| **21** | Expansão via doc oficial: 134 → 524 tools (15 skills, todas expandidas) |
| **20** | 15 skills viram MCP servers completos: 134 tools, smoke tests, `docs/mcps.md` |
| **19** | `automations-engine-poll` + `automations-engine-record-run` — daemon sem `service_role` na VPS |
| **17** | Automation Engine: `cfo_automation_engine.py` + 8 action types + systemd |
| **16** | Comando Central: `dashboard-snapshot` edge fn + `/dashboard-snapshot` |
| Antes | Sprints 1–15: skill library inicial (Omie, Bling, HubSpot, Asaas, etc.), painel Lovable, setup.sh, wacli, proactive watcher, relatórios, cobrança, CRM gateway |

---

## Marcos evoluiu assim

```
Sprint 1–5   → Alertas WhatsApp básicos (Omie + wacli)
Sprint 6–10  → Multi-ERP (Bling, Tiny, Granatum, VHSYS, Nibo, ContaAzul)
Sprint 11–15 → Multi-CRM (HubSpot, RD Station, PipeRun, Pipedrive)
Sprint 16–19 → Painel web + Automações + Supabase
Sprint 20–24 → MCP servers completos (1.280 tools)
Sprint 25–28 → Plug-and-play: zero SSH via painel + supabase multi-projeto
Sprint 29–33 → Cross-channel (WhatsApp Evolution + Telegram + pipeline unificado)
Sprint 34–37 → Admin via painel + Kommo CRM + MCP warmer + zero SSH total
Sprint 40–47 → Observabilidade + Alertas + Health + Backup + Memória portável
```
