#!/usr/bin/env bash
# connect.sh — Supabase Projects
#
# A conexão com projetos Supabase é gerenciada pelo painel web.
# Não há configuração manual nesta VPS.
#
# Para adicionar ou remover projetos:
#   1. Acesse o painel: https://seu-painel.lovable.app
#   2. Navegue para Configurações → Integrações → Supabase
#   3. Adicione seu projeto com URL + service_role_key
#
# O daemon cfo-supabase-sync.service sincronizará automaticamente
# (a cada 5 minutos) e registrará os MCPs em ~/.openclaw/openclaw.json.
#
# Para forçar sincronização imediata:
#   systemctl restart cfo-supabase-sync

set -euo pipefail

echo ""
echo "=== Supabase Projects Sync ==="
echo ""
echo "A conexão com projetos Supabase é gerenciada pelo painel web."
echo ""
echo "Para adicionar projetos:"
echo "  1. Acesse o painel Agente CFO"
echo "  2. Vá em Configurações → Integrações → Supabase"
echo "  3. Adicione o projeto com URL e service_role_key"
echo ""
echo "Para forçar sync imediato:"
echo "  systemctl restart cfo-supabase-sync"
echo ""
echo "Logs do sync:"
echo "  journalctl -u cfo-supabase-sync -f"
echo ""

systemctl is-active cfo-supabase-sync &>/dev/null && \
    echo "✓ cfo-supabase-sync está rodando" || \
    echo "⚠ cfo-supabase-sync não está rodando (systemctl start cfo-supabase-sync)"
