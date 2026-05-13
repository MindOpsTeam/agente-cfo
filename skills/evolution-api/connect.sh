#!/usr/bin/env bash
# connect.sh — Evolution API
# A configuração é 100% via painel web (Sprint 27 — zero SSH).
set -euo pipefail

echo ""
echo "=== Evolution API — WhatsApp Multi-Instância ==="
echo ""
echo "A configuração da Evolution API é feita no painel web."
echo ""
echo "Passos:"
echo "  1. Acesse o painel Agente CFO"
echo "  2. Vá em Configurações → WhatsApp → Evolution API"
echo "  3. Informe a URL base e API key da sua Evolution"
echo "  4. Crie as instâncias WhatsApp desejadas"
echo "  5. Leia o QR code que aparece no painel"
echo ""
echo "Pra forçar sync imediato:"
echo "  systemctl restart cfo-evolution-sync"
echo ""
echo "Logs:"
echo "  journalctl -u cfo-evolution-sync -f"
echo ""

systemctl is-active cfo-evolution-sync &>/dev/null && \
    echo "✓ cfo-evolution-sync está rodando" || \
    echo "⚠ cfo-evolution-sync não está rodando (systemctl start cfo-evolution-sync)"
