# Backup e Restore — Agente CFO

## Sprint 45 — Exportar e restaurar configuração com segurança

---

## Backup

```bash
# Backup sanitizado (sem tokens — seguro para compartilhar)
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/backup_config.sh

# Backup completo (com tokens — NUNCA compartilhe sem encriptar)
bash ~/.openclaw/workspace/skills/agente-cfo/scripts/backup_config.sh --include-secrets

# Backup em caminho específico
bash backup_config.sh --output ~/meu-backup.tar.gz
```

### O que inclui

| Arquivo no backup | Conteúdo | Sanitizado? |
|-------------------|---------|-------------|
| `openclaw.json` | Configuração do gateway (sem tokens por padrão) | ✓ (valores → `<REDACTED>`) |
| `env` | Variáveis de ambiente | ✓ (apenas URLs e flags preservadas) |
| `skills-list.txt` | Skills instaladas com hash git | Não sensível |
| `systemd-units.txt` | Services cfo-* ativos | Não sensível |
| `cron-jobs.json` | Cron jobs do OpenClaw | Não sensível |
| `mcp-servers.json` | MCP servers (env redactado) | ✓ |
| `metadata.json` | hostname, OS, versão, timestamp | Não sensível |

### Backup automático diário

Configurado via cron no setup.sh: todo dia às 03:00, salva em `~/.agente-cfo/backups/`.
Mantém últimos 7 backups automáticos (os mais antigos são removidos automaticamente).

```bash
# Ver backups disponíveis
ls -lh ~/.agente-cfo/backups/
```

---

## Restore

```bash
# Dry-run: mostra o que seria alterado sem aplicar
bash restore_config.sh ~/cfo-backup-20260515.tar.gz --dry-run

# Aplicar restore
bash restore_config.sh ~/cfo-backup-20260515.tar.gz

# Aplicar sem reiniciar services
bash restore_config.sh ~/cfo-backup-20260515.tar.gz --skip-services
```

### O que restaura

| Item | Comportamento |
|------|---------------|
| `openclaw.json` completo (com secrets) | Aplica diretamente + valida + backup do atual |
| `openclaw.json` sanitizado | Aplica só configs não-sensíveis; secrets precisam ser reconfigurados |
| Skills faltantes | Executa `self_update.sh` para instalar todas |
| Services | Reinicia `openclaw-gateway` após mudanças |
| Cron jobs | Informa quais existiam — restore manual via `openclaw cron list` |

### Segurança do restore

1. **Backup automático** do `openclaw.json` atual antes de aplicar (salvo como `.bak.restore`)
2. **Validação**: após aplicar `openclaw.json`, roda `openclaw config validate`; se inválido, reverte
3. **Idempotente**: pode ser rodado múltiplas vezes sem causar dano
4. **Sanity check**: arquivo deve conter "cfo" no nome (evita aplicar arquivo errado)

---

## Migração para nova VPS

```bash
# Na VPS original — backup COMPLETO
bash backup_config.sh --include-secrets --output ~/cfo-migration.tar.gz

# Transfere para nova VPS
scp ~/cfo-migration.tar.gz nova-vps:~/

# Na nova VPS — instala OpenClaw + setup básico
curl -sSL https://install.openclaw.ai | bash
# Depois...
bash restore_config.sh ~/cfo-migration.tar.gz
```

---

## Via painel (Sprint 46)

A edge function `backup-download` (JWT auth) permite baixar o backup diretamente
do painel sem SSH:
1. Painel chama `backup-download`
2. Edge fn aciona Marcos via `/hooks/agent` para rodar `backup_config.sh`
3. Marcos salva em `/tmp/backup.tar.gz`
4. Edge fn faz upload para bucket `cfo-backups` no Supabase Storage
5. Retorna signed URL temporária (15min TTL) para download
