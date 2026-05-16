#!/usr/bin/env bash
# panel_post_reply.sh — Helper unificado de resposta cross-channel.
#
# Marcos chama este script ao terminar um run de qualquer canal externo.
# Detecta o tipo de canal e usa o helper correto pra enviar a resposta.
#
# Uso:
#   bash panel_post_reply.sh "<channel>" "<external_id>" "<reply>" [thread_id] [run_id]
#
#   channel     : "whatsapp:principal" | "telegram:marcoscfo_bot" | "panel:..."
#   external_id : phone (WA) | chat_id (Telegram) | user_id (panel)
#   reply       : texto da resposta
#   thread_id   : (opcional) thread_id pra panel_reply.sh
#   run_id      : (opcional) run_id pra panel_reply.sh
#
# Exemplos:
#   bash panel_post_reply.sh "whatsapp:principal" "5548992044331" "Saldo: R$12.000"
#   bash panel_post_reply.sh "telegram:marcoscfo_bot" "987654321" "Faturamento OK"
#   bash panel_post_reply.sh "panel:user123" "" "Pronto!" "panel:u123" "run_456"

set -euo pipefail

CHANNEL="${1:-}"
EXTERNAL_ID="${2:-}"
REPLY="${3:-}"
THREAD_ID="${4:-}"
RUN_ID="${5:-}"

if [[ -z "$CHANNEL" || -z "$REPLY" ]]; then
    echo "Uso: $0 <channel> <external_id> <reply> [thread_id] [run_id]" >&2
    echo "  ex: $0 whatsapp:principal 5548992044331 'Saldo OK'" >&2
    exit 1
fi

WORKSPACE="${HOME}/.openclaw/workspace/skills"
CHANNEL_TYPE="${CHANNEL%%:*}"      # "whatsapp" | "telegram" | "panel"
CHANNEL_NAME="${CHANNEL#*:}"       # "principal" | "marcoscfo_bot" | "user123"

# ── 1. Envia pelo canal externo ───────────────────────────────────────────────

case "$CHANNEL_TYPE" in

    panel)
        # Canal painel — só grava no histórico (resposta já aparece via Supabase realtime)
        echo "✓ Canal painel — resposta via panel_reply.sh"
        ;;

    *)
        echo "AVISO: tipo de canal desconhecido: $CHANNEL_TYPE — só grava no painel" >&2
        ;;
esac

# ── 2. Grava no painel (histórico unificado) ──────────────────────────────────

if [[ -n "$THREAD_ID" && -n "$RUN_ID" ]]; then
    PANEL_REPLY="${WORKSPACE}/agente-cfo/scripts/panel_reply.sh"
    if [[ -f "$PANEL_REPLY" ]]; then
        bash "$PANEL_REPLY" "$THREAD_ID" "$RUN_ID" "$REPLY" "sent" || \
            echo "AVISO: panel_reply.sh falhou (não bloqueia)" >&2
    else
        echo "AVISO: panel_reply.sh não encontrado — histórico não gravado" >&2
    fi
fi

echo "✓ panel_post_reply concluído (channel=$CHANNEL, external_id=${EXTERNAL_ID:-n/a})"
