#!/usr/bin/env bash
# _thread_helpers.sh — Helpers para memoria de thread por contato (WhatsApp)
# NAO execute diretamente. Use: source "$SCRIPT_DIR/_thread_helpers.sh"

THREAD_DIR="${HOME}/.agente-cfo/memory/threads"

_thread_file() {
    local jid="$1"
    local safe_jid="${jid//\//_}"
    safe_jid="${safe_jid//:/_}"
    mkdir -p "$THREAD_DIR"
    echo "${THREAD_DIR}/${safe_jid}.md"
}

_append_thread() {
    local jid="$1" role="$2" content="$3"
    local thread_file
    thread_file=$(_thread_file "$jid")
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] [$role] $content" >> "$thread_file"
}

_read_thread() {
    # Le ultimas N linhas do thread (default 30)
    local jid="$1" lines="${2:-30}"
    local thread_file
    thread_file=$(_thread_file "$jid")
    if [[ -f "$thread_file" ]]; then
        tail -n "$lines" "$thread_file"
    fi
}
