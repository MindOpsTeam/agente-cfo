#!/usr/bin/env bash
# connect.sh — Telegram Bot
# A configuração é 100% via painel web (Sprint 34 — zero SSH).
set -euo pipefail

echo ""
echo "=== Telegram Bot — Agente CFO ==="
echo ""
echo "A configuração do Telegram é feita no painel web:"
echo ""
echo "  1. Fale com @BotFather no Telegram"
echo "  2. Digite /newbot e siga as instruções"
echo "  3. No painel: Configurações → Telegram → Adicionar bot"
echo "  4. Cole o token do BotFather"
echo ""
echo "Em até 30s o daemon registra o webhook automaticamente."
echo ""
echo "Para forçar sync imediato:"
echo "  systemctl restart cfo-telegram-sync"
echo ""
echo "Logs:"
echo "  journalctl -u cfo-telegram-sync -f"
echo ""

systemctl is-active cfo-telegram-sync &>/dev/null && \
    echo "✓ cfo-telegram-sync está rodando" || \
    echo "⚠ cfo-telegram-sync não está rodando (systemctl start cfo-telegram-sync)"
