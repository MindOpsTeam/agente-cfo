#!/usr/bin/env bash
# repare.sh — Re-pareamento guiado do WhatsApp via wacli
# Use quando wacli doctor reportar QR expirado ou desconexão.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_shared.sh
source "$SCRIPT_DIR/_shared.sh"

LOG_FILE="$LOG_DIR/repare.log"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== repare.sh iniciado em $TIMESTAMP ==="

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          Agente CFO — Re-pareamento WhatsApp             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Este assistente vai guiar você pelo processo de reconexão."
echo "Você precisará do seu celular com WhatsApp em mãos."
echo ""

# ── Verificar estado atual ────────────────────────────────────────────────────
echo "Verificando estado atual do WhatsApp..."
if wacli doctor 2>&1 | grep -qi "connected\|ok\|pareado"; then
    echo ""
    echo "✅ WhatsApp já está conectado. Nenhuma ação necessária."
    echo ""
    echo "Se continuar tendo problemas, execute:"
    echo "  wacli doctor --json"
    echo "=== repare.sh encerrado (já conectado) ==="
    exit 0
fi

echo ""
echo "⚠️  WhatsApp desconectado. Iniciando re-pareamento..."
echo ""
echo "INSTRUÇÃO:"
echo "  1. Abra o WhatsApp no seu celular"
echo "  2. Toque nos 3 pontinhos (⋮) no canto superior direito"
echo "  3. Selecione 'Dispositivos conectados'"
echo "  4. Toque em 'Conectar um dispositivo'"
echo "  5. Aponte a câmera para o QR code abaixo"
echo ""
echo "Pressione ENTER quando estiver pronto para exibir o QR code..."
read -r

# ── Iniciar auth ──────────────────────────────────────────────────────────────
echo "Iniciando autenticação wacli..."
echo "(O QR code aparecerá abaixo. Você tem ~60 segundos para escanear.)"
echo ""

if wacli auth; then
    echo ""
    echo "✅ Pareamento concluído com sucesso!"
    echo ""

    sleep 3
    echo "Verificando conexão..."
    if wacli doctor 2>&1 | grep -qi "connected\|ok"; then
        echo "✅ WhatsApp conectado e operacional."
        _panel_event "whatsapp_reconnected" "info" \
            "{\"detail\":\"re-pareamento manual concluído\"}"
    else
        echo "⚠️  Pareamento feito mas conexão instável. Aguarde 30 segundos e tente:"
        echo "  wacli doctor"
    fi
else
    echo ""
    echo "❌ Falha no pareamento. Possíveis causas:"
    echo "  • QR code expirou antes do escaneamento (tente novamente mais rápido)"
    echo "  • Problema de conectividade de rede neste servidor"
    echo "  • WhatsApp no celular desatualizado"
    echo ""
    echo "Tente executar este script novamente."

    _panel_event "whatsapp_disconnected" "error" \
        "{\"detail\":\"re-pareamento falhou\"}"

    echo "=== repare.sh encerrado com falha ==="
    exit 1
fi

echo "=== repare.sh encerrado com sucesso ==="
