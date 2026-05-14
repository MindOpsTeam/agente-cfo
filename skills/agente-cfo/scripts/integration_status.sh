#!/usr/bin/env bash
# integration_status.sh — Overview tabular de todas as integrações MCP.
#
# Uso: bash integration_status.sh
# Lê: ~/.openclaw/secrets/*.env + openclaw config get mcp.servers
# Testa: handshake JSON-RPC tools/list em cada mcp_server.py (timeout 5s)

set -euo pipefail

SECRETS_DIR="${HOME}/.openclaw/secrets"
WORKSPACE="${HOME}/.openclaw/workspace/skills"

# ── Helpers ──────────────────────────────────────────────────────────────────
_check() {
    local skill="$1"
    local secrets_ok="✗"
    local mcp_reg="✗"
    local mcp_resp="✗"
    local status="FAIL"
    local fail_reason=""

    # 1. Secrets
    local env_file="${SECRETS_DIR}/${skill}.env"
    if [[ -f "$env_file" ]]; then
        secrets_ok="✓"
    elif [[ "$skill" == supabase_* ]]; then
        secrets_ok="n/a"
    fi

    # 2. MCP registrado
    local mcp_entry
    mcp_entry=$(openclaw mcp show "$skill" --json 2>/dev/null || echo "")
    if [[ -n "$mcp_entry" && "$mcp_entry" != "null" ]]; then
        mcp_reg="✓"
    else
        fail_reason="mcp_not_registered"
    fi

    # 3. MCP responde
    local mcp_script="${WORKSPACE}/${skill}/mcp_server.py"
    if [[ "$mcp_reg" == "✓" ]]; then
        if [[ -f "$mcp_script" ]]; then
            # Monta env do .env file
            local env_args=()
            if [[ -f "$env_file" ]]; then
                while IFS= read -r line; do
                    [[ -z "$line" || "$line" == \#* ]] && continue
                    env_args+=("$line")
                done < "$env_file"
            fi

            local n_tools
            n_tools=$(
                env "${env_args[@]}" python3 "$mcp_script" 2>/dev/null <<< \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"status","version":"0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
                | timeout 5 python3 -c "
import sys, json
for line in sys.stdin:
    try:
        obj = json.loads(line.strip())
        if obj.get('id') == 2:
            print(len(obj.get('result',{}).get('tools',[])))
            sys.exit(0)
    except: pass
print('?')
" 2>/dev/null || echo "err"
            )
            case "$n_tools" in
                err|""|"?") mcp_resp="✗(err)"   ; fail_reason="${fail_reason:-mcp_error}" ;;
                *)           mcp_resp="✓(${n_tools})" ;;
            esac
        elif [[ "$skill" == supabase_* ]]; then
            command -v npx &>/dev/null && mcp_resp="n/a(npx)" || mcp_resp="✗(npx?)"
        else
            mcp_resp="✗(no_script)"
            fail_reason="${fail_reason:-no_mcp_script}"
        fi
    fi

    # Status final
    if [[ "$mcp_reg" == "✓" && "$mcp_resp" != "✗"* ]]; then
        status="PASS"
    else
        status="FAIL:${fail_reason}"
    fi

    printf "%-22s %-10s %-10s %-16s %s\n" "$skill" "$secrets_ok" "$mcp_reg" "$mcp_resp" "$status"
}

# ── Header ────────────────────────────────────────────────────────────────────
echo ""
printf "%-22s %-10s %-10s %-16s %s\n" "INTEGRATION" "SECRETS" "MCP_REG" "MCP_RESPONDS" "STATUS"
printf '%.0s─' {1..72}; echo

# ── Coleta skills ─────────────────────────────────────────────────────────────
declare -A seen

# a) Skills com .env em secrets/
if compgen -G "${SECRETS_DIR}/*.env" &>/dev/null; then
    for env_file in "${SECRETS_DIR}"/*.env; do
        skill=$(basename "$env_file" .env)
        # Pula arquivos internos (ex: hubspot_stages.json não é .env mas por precaução)
        [[ "$skill" == *"stages"* ]] && continue
        seen["$skill"]=1
        _check "$skill"
    done
fi

# b) MCP servers registrados que podem não ter .env (ex: supabase_*)
mcp_names=$(python3 - <<'PYEOF' 2>/dev/null
import json
from pathlib import Path
cfg = Path.home() / ".openclaw" / "openclaw.json"
if cfg.exists():
    data = json.loads(cfg.read_text())
    servers = data.get("mcp", {}).get("servers", {})
    for name in sorted(servers.keys()):
        print(name)
PYEOF
)
while IFS= read -r skill; do
    [[ -z "$skill" ]] && continue
    if [[ -z "${seen[$skill]+x}" ]]; then
        seen["$skill"]=1
        _check "$skill"
    fi
done <<< "$mcp_names"

# Se nenhuma integração encontrada
if [[ ${#seen[@]} -eq 0 ]]; then
    echo "  (nenhuma integração encontrada — adicione credenciais no painel)"
fi

# ── Gateway status ────────────────────────────────────────────────────────────
echo ""
GW=$(systemctl is-active openclaw-gateway 2>/dev/null || echo "unknown")
printf "Gateway: %s\n" "$GW"
echo ""
