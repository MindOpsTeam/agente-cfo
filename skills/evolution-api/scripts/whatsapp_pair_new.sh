#!/usr/bin/env bash
# whatsapp_pair_new.sh — Cria nova instância WhatsApp + obtém QR code via Evolution API.
# Faz upload do QR pro Supabase Storage e atualiza whatsapp_instances.
#
# Parte do SPRINT CHAN-1: pareamento WhatsApp 100% pelo painel, sem SSH.
#
# Uso:
#   bash whatsapp_pair_new.sh --instance <nome>
#
# Saída (stdout JSON):
#   {"success":true,"instance":"<name>","qr_url":"<supabase-storage-public-url>"}
#   {"success":false,"error":"<mensagem>"}
#
# Requer no ~/.agente-cfo/.env:
#   EVOLUTION_API_URL, EVOLUTION_API_KEY
#   PANEL_BASE_URL, PANEL_TOKEN          (Supabase project URL + service role key)
#   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
#
# Sprint CHAN-1 — 2026-05-25

set -euo pipefail

ENV_FILE="${HOME}/.agente-cfo/.env"
[[ -f "$ENV_FILE" ]] && { set -a; source "$ENV_FILE"; set +a; }

LOG_FILE="${HOME}/.agente-cfo/logs/whatsapp-pair.log"
mkdir -p "$(dirname "$LOG_FILE")"

_log() { printf '[%s] %s\n' "$(date +%FT%T)" "$*" >> "$LOG_FILE"; }
_ok()  { printf '{"success":true,"instance":"%s","qr_url":"%s"}\n' "$INSTANCE_NAME" "$QR_PUBLIC_URL"; }
_err() { printf '{"success":false,"error":"%s"}\n' "$1" >&2; _log "ERROR: $1"; exit 1; }

# ── Parse args ────────────────────────────────────────────────────────────────
INSTANCE_NAME=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --instance) INSTANCE_NAME="$2"; shift 2 ;;
        *) shift ;;
    esac
done

[[ -z "$INSTANCE_NAME" ]] && _err "argumento --instance obrigatorio"

# Valida nome: apenas alnum, hifens e underscores
if ! printf '%s' "$INSTANCE_NAME" | grep -qE '^[a-zA-Z0-9_-]{1,64}$'; then
    _err "nome de instancia invalido (use apenas letras, numeros, hifen, underscore; max 64 chars)"
fi

_log "whatsapp_pair_new START instance=$INSTANCE_NAME"

# ── Env vars obrigatórias ─────────────────────────────────────────────────────
EVOLUTION_API_URL="${EVOLUTION_API_URL:-}"
EVOLUTION_API_KEY="${EVOLUTION_API_KEY:-}"
SUPABASE_URL="${SUPABASE_URL:-${PANEL_BASE_URL:-}}"
SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-${PANEL_TOKEN:-}}"

[[ -z "$EVOLUTION_API_URL" ]] && _err "EVOLUTION_API_URL nao definida no .env"
[[ -z "$EVOLUTION_API_KEY" ]] && _err "EVOLUTION_API_KEY nao definida no .env"
[[ -z "$SUPABASE_URL" ]]      && _err "SUPABASE_URL (ou PANEL_BASE_URL) nao definida no .env"
[[ -z "$SUPABASE_SERVICE_ROLE_KEY" ]] && _err "SUPABASE_SERVICE_ROLE_KEY (ou PANEL_TOKEN) nao definida no .env"

# ── Tmpdir limpo no fim ────────────────────────────────────────────────────────
TMPDIR_WORK=$(mktemp -d)
trap 'rm -rf "$TMPDIR_WORK"' EXIT

QR_B64_FILE="$TMPDIR_WORK/qr.b64"
QR_PNG_FILE="$TMPDIR_WORK/qr.png"
RESP_FILE="$TMPDIR_WORK/evo_resp.json"

# ── 1. Evolution API /instance/create ─────────────────────────────────────────
_log "POST ${EVOLUTION_API_URL}/instance/create"

CREATE_PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'instanceName': '$INSTANCE_NAME',
    'qrcode': True,
    'integration': 'WHATSAPP-BAILEYS'
}))
")

HTTP_CODE=$(curl -s -o "$RESP_FILE" -w "%{http_code}" \
    --max-time 30 \
    -X POST "${EVOLUTION_API_URL%/}/instance/create" \
    -H "Content-Type: application/json" \
    -H "apikey: ${EVOLUTION_API_KEY}" \
    -d "$CREATE_PAYLOAD" 2>>"$LOG_FILE" || echo "000")

_log "Evolution /instance/create HTTP=$HTTP_CODE"

if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "201" ]]; then
    ERR_BODY=$(head -c 300 "$RESP_FILE" 2>/dev/null || echo "sem resposta")
    _err "Evolution API create falhou HTTP=$HTTP_CODE: $ERR_BODY"
fi

# ── 2. Extrai QR base64 da resposta ───────────────────────────────────────────
# Resposta pode estar em .qrcode.base64 ou .hash.qrcode ou .qrcode
QR_B64=$(python3 -c "
import sys, json
try:
    d = json.load(open('$RESP_FILE'))
    # Tenta múltiplos caminhos da resposta Evolution
    qr = (d.get('qrcode', {}) or {}).get('base64') or \
         (d.get('hash', {}) or {}).get('qrcode') or \
         d.get('qrcode') or ''
    # Remove prefixo data:image/png;base64,
    if isinstance(qr, str) and ',' in qr:
        qr = qr.split(',', 1)[1]
    print(qr)
except Exception as e:
    print('')
" 2>/dev/null || echo "")

if [[ -z "$QR_B64" ]]; then
    # Fallback: tenta buscar QR via endpoint dedicado
    _log "QR nao na resposta de create, tentando /instance/connect/$INSTANCE_NAME"
    HTTP_CODE2=$(curl -s -o "$RESP_FILE" -w "%{http_code}" \
        --max-time 20 \
        -X GET "${EVOLUTION_API_URL%/}/instance/connect/${INSTANCE_NAME}" \
        -H "apikey: ${EVOLUTION_API_KEY}" 2>>"$LOG_FILE" || echo "000")
    _log "Evolution /instance/connect HTTP=$HTTP_CODE2"

    QR_B64=$(python3 -c "
import sys, json
try:
    d = json.load(open('$RESP_FILE'))
    qr = (d.get('qrcode', {}) or {}).get('base64') or d.get('base64') or ''
    if isinstance(qr, str) and ',' in qr:
        qr = qr.split(',', 1)[1]
    print(qr)
except Exception as e:
    print('')
" 2>/dev/null || echo "")
fi

[[ -z "$QR_B64" ]] && _err "QR base64 nao encontrado na resposta da Evolution API"

# Salva base64 e decodifica PNG
printf '%s' "$QR_B64" > "$QR_B64_FILE"
if command -v base64 &>/dev/null; then
    base64 --decode "$QR_B64_FILE" > "$QR_PNG_FILE" 2>>"$LOG_FILE" || \
    base64 -d "$QR_B64_FILE" > "$QR_PNG_FILE" 2>>"$LOG_FILE"
else
    python3 -c "
import base64, sys
with open('$QR_B64_FILE') as f:
    data = f.read().strip()
with open('$QR_PNG_FILE', 'wb') as out:
    out.write(base64.b64decode(data))
" 2>>"$LOG_FILE"
fi

[[ ! -s "$QR_PNG_FILE" ]] && _err "Falha ao decodificar QR PNG"
_log "QR PNG gerado size=$(wc -c < "$QR_PNG_FILE") bytes"

# ── 3. Upload QR PNG pro Supabase Storage (bucket: qr-codes) ──────────────────
STORAGE_PATH="qr-codes/${INSTANCE_NAME}.png"
STORAGE_URL="${SUPABASE_URL%/}/storage/v1/object/${STORAGE_PATH}"

_log "Upload QR para Supabase Storage: $STORAGE_URL"

UPLOAD_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time 30 \
    -X POST "$STORAGE_URL" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: image/png" \
    -H "x-upsert: true" \
    --data-binary "@${QR_PNG_FILE}" 2>>"$LOG_FILE" || echo "000")

_log "Supabase Storage upload HTTP=$UPLOAD_CODE"

# Aceita 200 ou 409 (já existe, upsert ativo)
if [[ "$UPLOAD_CODE" != "200" && "$UPLOAD_CODE" != "201" && "$UPLOAD_CODE" != "409" ]]; then
    _err "Upload QR falhou HTTP=$UPLOAD_CODE"
fi

QR_PUBLIC_URL="${SUPABASE_URL%/}/storage/v1/object/public/${STORAGE_PATH}"
_log "QR URL publica: $QR_PUBLIC_URL"

# ── 4. Atualiza whatsapp_instances via PostgREST ───────────────────────────────
_log "Upserting whatsapp_instances instance_name=$INSTANCE_NAME status=waiting_scan"

UPSERT_PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
    'instance_name': '$INSTANCE_NAME',
    'qr_code_b64': '$QR_B64',
    'status': 'waiting_scan',
    'updated_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z'
}))
")

UPSERT_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time 20 \
    -X POST "${SUPABASE_URL%/}/rest/v1/whatsapp_instances" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Content-Type: application/json" \
    -H "Prefer: resolution=merge-duplicates" \
    -d "$UPSERT_PAYLOAD" 2>>"$LOG_FILE" || echo "000")

_log "PostgREST upsert HTTP=$UPSERT_CODE"

if [[ "$UPSERT_CODE" != "200" && "$UPSERT_CODE" != "201" ]]; then
    _log "WARN: upsert whatsapp_instances falhou HTTP=$UPSERT_CODE (QR ja disponivel no Storage)"
fi

# ── 5. Saída ──────────────────────────────────────────────────────────────────
_log "whatsapp_pair_new DONE instance=$INSTANCE_NAME qr_url=$QR_PUBLIC_URL"
_ok
