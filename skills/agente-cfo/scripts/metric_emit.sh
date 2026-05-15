#!/usr/bin/env bash
# metric_emit.sh — Emite uma métrica no metrics.jsonl local.
#
# Uso: bash metric_emit.sh <metric_name> <value_ms> [meta_json]
#
#   metric_name : nome da métrica (ex: "hubspot.list_deals")
#   value_ms    : tempo em ms ou qualquer valor numérico
#   meta_json   : (opcional) JSON extra com contexto
#
# Exemplos:
#   bash metric_emit.sh "hubspot.list_deals" 1234 '{"deals_returned":23}'
#   bash metric_emit.sh "omie.clientes_listar" 890 '{"pages":3}'
#   bash metric_emit.sh "automation.run" 12500 '{"automation":"relatorio_semanal","status":"success"}'
#
# O metrics_publisher.py lê esse arquivo e publica no painel a cada 60s.

set -euo pipefail

METRIC_NAME="${1:-}"
VALUE_MS="${2:-0}"
META_JSON="${3:-{}}"

if [[ -z "$METRIC_NAME" ]]; then
    echo "Uso: $0 <metric_name> <value_ms> [meta_json]" >&2
    exit 1
fi

# Valida que metric_name é string simples (sem injection)
if ! echo "$METRIC_NAME" | grep -qE '^[a-zA-Z0-9._:-]+$'; then
    echo "ERRO: metric_name inválido (use apenas a-z, A-Z, 0-9, ., _, :, -)" >&2
    exit 1
fi

# Valida que VALUE_MS é número
if ! echo "$VALUE_MS" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
    echo "ERRO: value_ms deve ser número" >&2
    exit 1
fi

METRICS_JSONL="${HOME}/.agente-cfo/logs/metrics.jsonl"
mkdir -p "$(dirname "$METRICS_JSONL")"

# Obtém timestamp ISO
TS=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())")

# Monta JSON e enriquece meta com tool_name
RECORD=$(python3 -c "
import sys, json
name = sys.argv[1]
value = float(sys.argv[2])
try:
    meta = json.loads(sys.argv[3])
except:
    meta = {}
meta['tool_name'] = name  # sempre inclui tool_name pro aggregator
rec = {
    'ts': sys.argv[4],
    'daemon': 'marcos_tool',
    'cycle_ms': int(value),
    'errors': 1 if meta.get('error') else 0,
    'meta': meta,
}
print(json.dumps(rec))
" "$METRIC_NAME" "$VALUE_MS" "$META_JSON" "$TS")

echo "$RECORD" >> "$METRICS_JSONL"
echo "✓ métrica emitida: $METRIC_NAME=${VALUE_MS}ms" >&2
