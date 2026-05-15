#!/usr/bin/env bash
# admin_action.sh — Interface whitelisted de comandos OpenClaw/systemd.
#
# Sprint 37 — zero SSH pra TUDO: painel/Marcos chama este script pra
# executar ações administrativas com validação rigorosa (sem injection).
#
# Uso:
#   echo '<json>' | bash admin_action.sh
#   bash admin_action.sh '<json>'
#
# O JSON deve ter:
#   { "action": "<nome>", "key"?: "...", "value"?: ..., "service"?: "...", ... }
#
# Retorna JSON em stdout:
#   { "ok": true|false, "output": "...", "error": "...", "took_ms": N }
#
# Actions disponíveis (whitelist exaustiva):
#   openclaw_config_get     { key }
#   openclaw_config_set     { key, value }
#   openclaw_config_unset   { key }
#   openclaw_config_validate
#   openclaw_plugins_list
#   openclaw_plugins_install  { plugin }
#   openclaw_plugins_enable   { plugin }
#   openclaw_plugins_disable  { plugin }
#   openclaw_mcp_list
#   openclaw_mcp_set    { name, value_json }
#   openclaw_mcp_unset  { name }
#   openclaw_status
#   openclaw_health
#   openclaw_doctor
#   systemctl_restart   { service }  — só prefixo cfo- | openclaw- | cloudflared-cfo
#   systemctl_status    { service }
#   systemctl_start     { service }
#   systemctl_stop      { service }
#   service_logs        { service, lines? }
#   mcp_sync_now
#   self_update
#   whatsapp_pair_start  (inicia pareamento Baileys via OpenClaw nativo)
#   whatsapp_pair_status (retorna estado do pareamento)
#   whatsapp_pair_qr     (retorna QR ASCII art para escaneamento)
#   whatsapp_pair_cancel (cancela processo de pareamento)
#   whatsapp_status      (status do canal WhatsApp no gateway)
#   whatsapp_send        { chat_id, text }

set -euo pipefail

# ── Setup ─────────────────────────────────────────────────────────────────────
WORKSPACE="${HOME}/.openclaw/workspace/skills/agente-cfo/scripts"
ENV_FILE="${HOME}/.agente-cfo/.env"
[[ -f "$ENV_FILE" ]] && source "$ENV_FILE" 2>/dev/null || true

t0=$(python3 -c "import time; print(int(time.time()*1000))")

# ── JSON output helpers ───────────────────────────────────────────────────────
_result() {
    local ok="$1" output="$2" error="${3:-}" 
    local t1; t1=$(python3 -c "import time; print(int(time.time()*1000))")
    local took_ms=$((t1 - t0))
    # Escapa aspas duplas no output
    local out_safe; out_safe=$(printf '%s' "$output" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo '"<encode error>"')
    if [[ -n "$error" ]]; then
        local err_safe; err_safe=$(printf '%s' "$error" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo '"<encode error>"')
        printf '{"ok":%s,"output":%s,"error":%s,"took_ms":%d}\n' "$ok" "$out_safe" "$err_safe" "$took_ms"
    else
        printf '{"ok":%s,"output":%s,"took_ms":%d}\n' "$ok" "$out_safe" "$took_ms"
    fi
}

_ok()  { _result "true"  "$1"; }
_err() { _result "false" "" "$1"; }

# ── Lê input JSON ─────────────────────────────────────────────────────────────
if [[ $# -ge 1 ]]; then
    INPUT="$1"
else
    INPUT="$(cat)"
fi

if [[ -z "$INPUT" ]]; then
    _err "input JSON vazio"
    exit 0
fi

# Extrai campos do JSON via Python (sem eval, sem injection)
_get() {
    local field="$1"
    python3 -c "
import sys, json
try:
    d = json.loads(sys.argv[1])
    v = d.get(sys.argv[2], '')
    if isinstance(v, (dict, list)):
        print(json.dumps(v))
    else:
        print(str(v) if v is not None else '')
except Exception as e:
    print('')
" "$INPUT" "$field" 2>/dev/null || echo ""
}

ACTION="$(_get action)"
if [[ -z "$ACTION" ]]; then
    _err "campo 'action' obrigatório"
    exit 0
fi

# ── Whitelist de serviços systemd ─────────────────────────────────────────────
_validate_service() {
    local svc="$1"
    # Só permite prefixos seguros
    if [[ "$svc" =~ ^(cfo-|openclaw-|cloudflared-cfo)[a-z0-9._-]+$ ]] || \
       [[ "$svc" == "openclaw-gateway" ]] || \
       [[ "$svc" == "cloudflared-cfo" ]]; then
        return 0
    fi
    return 1
}

# ── Despacho de ações ─────────────────────────────────────────────────────────

case "$ACTION" in

    # ── openclaw config ───────────────────────────────────────────────────────
    openclaw_config_get)
        KEY="$(_get key)"
        [[ -z "$KEY" ]] && { _err "key obrigatório"; exit 0; }
        OUT=$(openclaw config get "$KEY" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_config_set)
        KEY="$(_get key)"
        VALUE="$(_get value)"
        [[ -z "$KEY" ]] && { _err "key obrigatório"; exit 0; }
        # Detecta se value é string simples ou JSON
        IS_JSON=$(python3 -c "
import sys, json
v = sys.argv[1]
try:
    json.loads(v)
    print('true')
except:
    print('false')
" "$VALUE" 2>/dev/null || echo "false")
        if [[ "$IS_JSON" == "true" ]]; then
            OUT=$(openclaw config set "$KEY" "$VALUE" --strict-json 2>&1)
        else
            OUT=$(openclaw config set "$KEY" "$VALUE" 2>&1)
        fi
        [[ $? -eq 0 ]] && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_config_unset)
        KEY="$(_get key)"
        [[ -z "$KEY" ]] && { _err "key obrigatório"; exit 0; }
        OUT=$(openclaw config unset "$KEY" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_config_validate)
        OUT=$(openclaw config validate 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    # ── openclaw plugins ──────────────────────────────────────────────────────
    openclaw_plugins_list)
        OUT=$(openclaw plugins list 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_plugins_install)
        PLUGIN="$(_get plugin)"
        [[ -z "$PLUGIN" ]] && { _err "plugin obrigatório"; exit 0; }
        # Valida: só permite nomes sem espaços/injection
        if ! echo "$PLUGIN" | grep -qE '^[a-zA-Z0-9@/_:.-]+$'; then
            _err "nome de plugin inválido (chars não permitidos)"
            exit 0
        fi
        OUT=$(openclaw plugins install "$PLUGIN" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_plugins_enable)
        PLUGIN="$(_get plugin)"
        [[ -z "$PLUGIN" ]] && { _err "plugin obrigatório"; exit 0; }
        OUT=$(openclaw plugins enable "$PLUGIN" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_plugins_disable)
        PLUGIN="$(_get plugin)"
        [[ -z "$PLUGIN" ]] && { _err "plugin obrigatório"; exit 0; }
        OUT=$(openclaw plugins disable "$PLUGIN" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    # ── openclaw mcp ──────────────────────────────────────────────────────────
    openclaw_mcp_list)
        OUT=$(openclaw mcp list 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_mcp_set)
        NAME="$(_get name)"
        VAL_JSON="$(_get value_json)"
        [[ -z "$NAME" || -z "$VAL_JSON" ]] && { _err "name e value_json obrigatórios"; exit 0; }
        # Valida que name é slug simples
        if ! echo "$NAME" | grep -qE '^[a-zA-Z0-9_-]+$'; then
            _err "name inválido"
            exit 0
        fi
        OUT=$(openclaw mcp set "$NAME" "$VAL_JSON" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_mcp_unset)
        NAME="$(_get name)"
        [[ -z "$NAME" ]] && { _err "name obrigatório"; exit 0; }
        OUT=$(openclaw mcp unset "$NAME" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    # ── openclaw status/health/doctor ────────────────────────────────────────
    openclaw_status)
        OUT=$(openclaw status 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_health)
        OUT=$(openclaw health 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    openclaw_doctor)
        OUT=$(openclaw doctor 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    # ── systemd service control ───────────────────────────────────────────────
    systemctl_restart)
        SVC="$(_get service)"
        [[ -z "$SVC" ]] && { _err "service obrigatório"; exit 0; }
        if ! _validate_service "$SVC"; then
            _err "serviço '$SVC' não permitido (só cfo-* ou openclaw-* ou cloudflared-cfo)"
            exit 0
        fi
        if ! command -v systemctl &>/dev/null; then
            # macOS: tenta openclaw gateway restart se for o gateway
            if [[ "$SVC" == "openclaw-gateway" ]]; then
                OUT=$(openclaw gateway restart 2>&1) && _ok "$OUT" || _err "$OUT"
            else
                _err "systemctl não disponível neste host"
            fi
            exit 0
        fi
        OUT=$(systemctl restart "$SVC" 2>&1) && _ok "reiniciado: $SVC" || _err "$OUT"
        ;;

    systemctl_start)
        SVC="$(_get service)"
        [[ -z "$SVC" ]] && { _err "service obrigatório"; exit 0; }
        _validate_service "$SVC" || { _err "serviço '$SVC' não permitido"; exit 0; }
        command -v systemctl &>/dev/null || { _err "systemctl não disponível"; exit 0; }
        OUT=$(systemctl start "$SVC" 2>&1) && _ok "iniciado: $SVC" || _err "$OUT"
        ;;

    systemctl_stop)
        SVC="$(_get service)"
        [[ -z "$SVC" ]] && { _err "service obrigatório"; exit 0; }
        _validate_service "$SVC" || { _err "serviço '$SVC' não permitido"; exit 0; }
        command -v systemctl &>/dev/null || { _err "systemctl não disponível"; exit 0; }
        OUT=$(systemctl stop "$SVC" 2>&1) && _ok "parado: $SVC" || _err "$OUT"
        ;;

    systemctl_status)
        SVC="$(_get service)"
        [[ -z "$SVC" ]] && { _err "service obrigatório"; exit 0; }
        _validate_service "$SVC" || { _err "serviço '$SVC' não permitido"; exit 0; }
        if command -v systemctl &>/dev/null; then
            OUT=$(systemctl status "$SVC" --no-pager 2>&1) && _ok "$OUT" || _ok "$OUT"
        else
            # macOS fallback: ps
            OUT=$(ps aux | grep -i "$SVC" | grep -v grep | head -5 || echo "não encontrado")
            _ok "$OUT"
        fi
        ;;

    # ── Logs ──────────────────────────────────────────────────────────────────
    service_logs)
        SVC="$(_get service)"
        LINES="$(_get lines)"
        LINES="${LINES:-50}"
        [[ -z "$SVC" ]] && { _err "service obrigatório"; exit 0; }
        _validate_service "$SVC" || { _err "serviço '$SVC' não permitido"; exit 0; }
        # Valida LINES é número
        if ! echo "$LINES" | grep -qE '^[0-9]+$' || [[ "$LINES" -gt 500 ]]; then
            _err "lines deve ser número entre 1 e 500"
            exit 0
        fi
        if command -v journalctl &>/dev/null; then
            OUT=$(journalctl -u "$SVC" -n "$LINES" --no-pager 2>&1) && _ok "$OUT" || _err "$OUT"
        else
            # macOS fallback: lê arquivo de log
            LOG_FILE="${HOME}/.agente-cfo/logs/${SVC#cfo-}.log"
            if [[ -f "$LOG_FILE" ]]; then
                OUT=$(tail -n "$LINES" "$LOG_FILE") && _ok "$OUT" || _err "erro lendo log"
            else
                _err "journalctl não disponível e log não encontrado: $LOG_FILE"
            fi
        fi
        ;;

    # ── Helpers internos ──────────────────────────────────────────────────────
    mcp_sync_now)
        SCRIPT="${WORKSPACE}/mcp_sync_now.sh"
        if [[ ! -f "$SCRIPT" ]]; then
            _err "mcp_sync_now.sh não encontrado"
            exit 0
        fi
        OUT=$(bash "$SCRIPT" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    self_update)
        SCRIPT="${WORKSPACE}/self_update.sh"
        if [[ ! -f "$SCRIPT" ]]; then
            _err "self_update.sh não encontrado"
            exit 0
        fi
        OUT=$(bash "$SCRIPT" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    # ── WhatsApp Baileys (Sprint 51) ───────────────────────────────────────────
    whatsapp_pair_start)
        HELPER="${WORKSPACE}/whatsapp_pair_helper.py"
        if [[ ! -f "$HELPER" ]]; then
            _err "whatsapp_pair_helper.py não encontrado"
            exit 0
        fi
        OUT=$(python3 "$HELPER" start 2>/dev/null) && _ok "$OUT" || _err "Falha ao iniciar pareamento"
        ;;

    whatsapp_pair_status)
        HELPER="${WORKSPACE}/whatsapp_pair_helper.py"
        if [[ ! -f "$HELPER" ]]; then
            _err "whatsapp_pair_helper.py não encontrado"
            exit 0
        fi
        OUT=$(python3 "$HELPER" status 2>/dev/null) && _ok "$OUT" || _err "Falha ao ler status"
        ;;

    whatsapp_pair_qr)
        # Retorna o QR ASCII art se status=qr_ready
        STATE_FILE="/tmp/cfo-whatsapp-pair.json"
        if [[ ! -f "$STATE_FILE" ]]; then
            _err "Nenhum pareamento em andamento (arquivo de estado não encontrado)"
            exit 0
        fi
        STATUS=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('status','idle'))" 2>/dev/null || echo "")
        if [[ "$STATUS" == "qr_ready" ]]; then
            QR=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('qr_ascii',''))" 2>/dev/null || echo "")
            _ok "$QR"
        elif [[ "$STATUS" == "connected" ]]; then
            _ok '{"status":"connected","message":"WhatsApp já conectado — não há QR para mostrar"}'
        else
            _err "QR não disponível (status: $STATUS). Execute whatsapp_pair_start primeiro."
        fi
        ;;

    whatsapp_pair_cancel)
        HELPER="${WORKSPACE}/whatsapp_pair_helper.py"
        if [[ ! -f "$HELPER" ]]; then
            _err "whatsapp_pair_helper.py não encontrado"
            exit 0
        fi
        OUT=$(python3 "$HELPER" cancel 2>/dev/null) && _ok "$OUT" || _err "Falha ao cancelar"
        ;;

    whatsapp_status)
        OUT=$(openclaw channels status 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    whatsapp_send)
        CHAT_ID="$(_get chat_id)"
        TEXT="$(_get text)"
        [[ -z "$CHAT_ID" || -z "$TEXT" ]] && { _err "chat_id e text obrigatórios"; exit 0; }
        # Valida chat_id: apenas dígitos, letras, @ e +
        if ! echo "$CHAT_ID" | grep -qE '^[0-9@+.a-zA-Z_-]+$'; then
            _err "chat_id inválido"
            exit 0
        fi
        # Usa openclaw agent para enviar (via sessions_send ou message send)
        OUT=$(openclaw message send --to "$CHAT_ID" --text "$TEXT" 2>&1) && _ok "$OUT" || _err "$OUT"
        ;;

    # ── Marcos Context (Sprint 53) ────────────────────────────────────────────
    marcos_context_get)
        CHANNEL="$(_get channel)"
        USER_NAME="$(_get user)"
        REGEN="$(_get regenerate)"
        SCRIPT="${WORKSPACE}/marcos_context.py"
        if [[ ! -f "$SCRIPT" ]]; then
            _err "marcos_context.py não encontrado"
            exit 0
        fi
        REGEN_FLAG=""
        [[ "$REGEN" == "true" ]] && REGEN_FLAG="--regen"
        OUT=$(python3 "$SCRIPT" \
            --channel "${CHANNEL:-panel}" \
            --user "${USER_NAME:-}" \
            --json \
            ${REGEN_FLAG} 2>/dev/null) && _ok "$OUT" || _err "Falha ao gerar context"
        ;;

    marcos_capabilities_update)
        SCRIPT="${WORKSPACE}/update_capabilities.py"
        if [[ ! -f "$SCRIPT" ]]; then
            _err "update_capabilities.py não encontrado"
            exit 0
        fi
        OUT=$(python3 "$SCRIPT" 2>&1 | tail -5) && _ok "$OUT" || _err "$OUT"
        ;;

    # ── Ação desconhecida ──────────────────────────────────────────────────────
    *)
        VALID_ACTIONS=(
            "openclaw_config_get" "openclaw_config_set" "openclaw_config_unset"
            "openclaw_config_validate" "openclaw_plugins_list"
            "openclaw_plugins_install" "openclaw_plugins_enable" "openclaw_plugins_disable"
            "openclaw_mcp_list" "openclaw_mcp_set" "openclaw_mcp_unset"
            "openclaw_status" "openclaw_health" "openclaw_doctor"
            "systemctl_restart" "systemctl_start" "systemctl_stop" "systemctl_status"
            "service_logs" "mcp_sync_now" "self_update"
            "whatsapp_pair_start" "whatsapp_pair_status" "whatsapp_pair_qr"
            "whatsapp_pair_cancel" "whatsapp_status" "whatsapp_send"
            "marcos_context_get" "marcos_capabilities_update"
        )
        VALID_STR=$(printf '"%s" ' "${VALID_ACTIONS[@]}")
        _err "ação '$ACTION' desconhecida. Actions válidas: ${VALID_STR}"
        ;;
esac
