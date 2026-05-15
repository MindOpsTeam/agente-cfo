#!/usr/bin/env bash
# marcos_learn.sh — Feedback loop: Marcos aprende com cada conversa.
#
# Lê JSON via stdin ou argumento e extrai aprendizados usando Anthropic Haiku.
# Salva em ~/.openclaw/memory/ e atualiza índice.
#
# Uso:
#   echo '<json>' | bash marcos_learn.sh
#   bash marcos_learn.sh '<json>'
#
# Input JSON:
#   {
#     "thread_id": "panel:<user>",
#     "user_message": "<pergunta do usuário>",
#     "marcos_response": "<resposta de Marcos>",
#     "tools_used": ["asaas_charges_list"],
#     "duration_ms": 28000,
#     "channel": "panel"
#   }
#
# Desabilitar: MARCOS_LEARN_DISABLED=1 bash marcos_learn.sh ...
#
# Exit 0 = aprendizados extraídos, Exit 1 = nenhum/erro (não crítico)

set -euo pipefail

# ── Opt-out ───────────────────────────────────────────────────────────────────
if [[ "${MARCOS_LEARN_DISABLED:-0}" == "1" ]]; then
    exit 0
fi

# ── Setup ─────────────────────────────────────────────────────────────────────
ENV_FILE="${HOME}/.agente-cfo/.env"
[[ -f "$ENV_FILE" ]] && set -a && source "$ENV_FILE" && set +a 2>/dev/null || true

MEM_DIR="${HOME}/.openclaw/memory/learned"
LOG_FILE="${HOME}/.agente-cfo/logs/marcos-learn.log"
INDEX_FILE="${HOME}/.openclaw/memory/learned/_index.json"
MAX_INDEX_SIZE=200  # máximo de entradas no índice

mkdir -p "$MEM_DIR"

_log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [marcos-learn] $*" >> "$LOG_FILE" 2>/dev/null || true; }

# ── Lê input ──────────────────────────────────────────────────────────────────
if [[ $# -ge 1 ]]; then
    INPUT="$1"
else
    INPUT="$(cat)"
fi

if [[ -z "$INPUT" ]]; then
    _log "Input vazio — abortando"
    exit 1
fi

# Extrai campos do JSON
_get() {
    python3 -c "
import sys, json
try:
    d = json.loads(sys.argv[1])
    v = d.get(sys.argv[2], '')
    if isinstance(v, (list, dict)):
        print(json.dumps(v))
    else:
        print(str(v) if v else '')
except:
    print('')
" "$INPUT" "$1" 2>/dev/null || echo ""
}

THREAD_ID="$(_get thread_id)"
USER_MSG="$(_get user_message)"
MARCOS_RESP="$(_get marcos_response)"
TOOLS="$(_get tools_used)"
CHANNEL="$(_get channel)"

# Validação mínima
if [[ -z "$USER_MSG" || -z "$MARCOS_RESP" ]]; then
    _log "user_message ou marcos_response vazios — abortando"
    exit 1
fi

# Limita tamanho para economizar tokens
USER_MSG_TRUNC="${USER_MSG:0:500}"
MARCOS_RESP_TRUNC="${MARCOS_RESP:0:800}"

# ── Verifica API key ──────────────────────────────────────────────────────────
ANTHROPIC_KEY="${ANTHROPIC_API_KEY:-}"
if [[ -z "$ANTHROPIC_KEY" ]]; then
    _log "ANTHROPIC_API_KEY não encontrada — learn desabilitado"
    exit 0  # Falha silenciosa (sem key = feature desabilitada)
fi

# ── Chama Haiku pra extrair aprendizados ──────────────────────────────────────
PROMPT="Analise esta interação entre um usuário e seu CFO virtual Marcos.
Extraia até 3 aprendizados úteis e reutilizáveis para conversas futuras.

Retorne APENAS JSON no formato:
[{\"tag\": \"preferência|terminologia|workflow|fato\", \"content\": \"...\", \"evidence\": \"...\"}]

Regras:
- Só extraia aprendizados ÚTEIS e REUTILIZÁVEIS (padrões, preferências, terminologia específica)
- NÃO extraia coisas óbvias ou muito específicas de um único evento
- NÃO extraia números ou valores que mudam (saldo atual, data de hoje etc)
- Se não há aprendizado útil, retorne []
- content deve ser uma afirmação clara (max 100 chars)
- evidence deve ser trecho curto da conversa que justifica (max 80 chars)

Tags:
- preferência: como o dono prefere ser atendido (formato, frequência, etc)
- terminologia: termos que o dono usa para coisas específicas
- workflow: sequência de ações recorrentes do dono
- fato: fato estável sobre a empresa/dono (nome do sócio, nome fantasia, etc)

Usuário: $USER_MSG_TRUNC

Marcos: $MARCOS_RESP_TRUNC"

HAIKU_RESP=$(python3 -c "
import json, urllib.request, os, sys

payload = {
    'model': 'claude-haiku-4-5',
    'max_tokens': 500,
    'messages': [{'role': 'user', 'content': sys.argv[1]}]
}

req = urllib.request.Request(
    'https://api.anthropic.com/v1/messages',
    data=json.dumps(payload).encode(),
    headers={
        'x-api-key': os.environ['ANTHROPIC_API_KEY'],
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
    },
    method='POST'
)

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
        text = data.get('content', [{}])[0].get('text', '[]')
        # Extrai JSON mesmo se vier com code fences
        import re
        m = re.search(r'\[.*?\]', text, re.DOTALL)
        if m:
            print(m.group(0).strip())
        else:
            print('[]')
except Exception as e:
    print('[]')
    print(str(e), file=sys.stderr)
" "$PROMPT" 2>/tmp/marcos-learn-err.txt)

if [[ -z "$HAIKU_RESP" || "$HAIKU_RESP" == "[]" ]]; then
    _log "Nenhum aprendizado extraído para thread $THREAD_ID"
    exit 0
fi

# ── Salva aprendizados ────────────────────────────────────────────────────────
NOW_ISO=$(python3 -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat())")

SAVED=$(python3 -c "
import json, uuid, os, sys
from pathlib import Path

try:
    learnings = json.loads(sys.argv[1])
except:
    print(0)
    sys.exit(0)

if not isinstance(learnings, list):
    print(0)
    sys.exit(0)

mem_dir = Path.home() / '.openclaw' / 'memory' / 'learned'
mem_dir.mkdir(parents=True, exist_ok=True)

saved = 0
saved_ids = []
for item in learnings[:3]:  # max 3 por run
    tag = item.get('tag', 'fato')
    content = item.get('content', '')
    evidence = item.get('evidence', '')
    if not content or len(content) < 10:
        continue
    
    # Validação básica: só tags conhecidas
    if tag not in ('preferência', 'terminologia', 'workflow', 'fato'):
        tag = 'fato'
    
    entry_id = str(uuid.uuid4())
    entry = {
        'id': entry_id,
        'tag': tag,
        'content': content[:120],
        'evidence': evidence[:100],
        'created_at': sys.argv[2],
        'thread_id': sys.argv[3],
        'channel': sys.argv[4],
        'tools_used': json.loads(sys.argv[5]) if sys.argv[5] else [],
        'usage_count': 0,
    }
    
    # Salva arquivo individual
    (mem_dir / f'{entry_id}.json').write_text(json.dumps(entry, ensure_ascii=False, indent=2))
    saved_ids.append(entry_id)
    saved += 1

# Atualiza índice
index_file = mem_dir / '_index.json'
try:
    index = json.loads(index_file.read_text())
except:
    index = {'entries': [], 'total': 0}

# Prepend novas entradas (FIFO)
index['entries'] = saved_ids + index['entries']
max_size = int(sys.argv[6])
if len(index['entries']) > max_size:
    # Remove mais antigas
    to_remove = index['entries'][max_size:]
    index['entries'] = index['entries'][:max_size]
    for old_id in to_remove:
        old_file = mem_dir / f'{old_id}.json'
        try:
            old_data = json.loads(old_file.read_text())
            # Preserva fatos permanentemente
            if old_data.get('tag') != 'fato':
                old_file.unlink(missing_ok=True)
        except:
            pass

index['total'] = index.get('total', 0) + saved
index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2))

print(saved)
" "$HAIKU_RESP" "$NOW_ISO" "$THREAD_ID" "$CHANNEL" "$TOOLS" "$MAX_INDEX_SIZE" 2>/tmp/marcos-learn-err.txt)

if [[ "${SAVED:-0}" -gt "0" ]]; then
    _log "$SAVED aprendizado(s) salvos para thread $THREAD_ID (channel=$CHANNEL)"
else
    _log "0 aprendizados válidos extraídos"
fi
