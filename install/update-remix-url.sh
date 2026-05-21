#!/usr/bin/env bash
# update-remix-url.sh — Atualiza a URL de Remix do Lovable em README e landing
#
# Uso:
#   bash install/update-remix-url.sh
#
# Requer: install/REMIX_URL.txt com a linha:
#   REMIX_URL=https://lovable.dev/projects/<id>/remix
#
# Atualiza automaticamente:
#   - README.md
#   - src/routes/install.tsx
#   - docs/CLIENTE.md

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMIX_URL_FILE="$REPO_DIR/install/REMIX_URL.txt"

# ── Verificar arquivo de config ───────────────────────────────────────────────
if [[ ! -f "$REMIX_URL_FILE" ]]; then
    echo "❌ Arquivo não encontrado: $REMIX_URL_FILE"
    echo ""
    echo "Crie o arquivo com:"
    echo "  echo 'REMIX_URL=https://lovable.dev/projects/SEU-ID/remix' > install/REMIX_URL.txt"
    echo ""
    echo "Veja install/REMIX_URL.example.txt para instruções completas."
    exit 1
fi

# shellcheck source=/dev/null
source "$REMIX_URL_FILE"

if [[ -z "${REMIX_URL:-}" ]]; then
    echo "❌ REMIX_URL não definida em $REMIX_URL_FILE"
    echo "   Formato esperado: REMIX_URL=https://lovable.dev/projects/<id>/remix"
    exit 1
fi

# Validar formato
if ! echo "$REMIX_URL" | grep -qE '^https://lovable\.dev/projects/[a-zA-Z0-9_-]+/remix$'; then
    echo "⚠️  REMIX_URL não parece ser uma URL de Remix válida do Lovable:"
    echo "   $REMIX_URL"
    echo ""
    read -rp "Continuar mesmo assim? (s/N): " _ans
    [[ "${_ans:-n}" =~ ^[Ss]$ ]] || { echo "Abortado."; exit 1; }
fi

echo ""
echo "🔄 Atualizando URL de Remix: $REMIX_URL"
echo ""

UPDATED=0

# ── 1. README.md ─────────────────────────────────────────────────────────────
README="$REPO_DIR/README.md"
if [[ -f "$README" ]]; then
    # Substitui qualquer URL lovable.dev/projects/*/remix existente
    if grep -qE 'lovable\.dev/projects/[^)]+/remix' "$README"; then
        sed -i.bak -E "s|https://lovable\\.dev/projects/[^)\"']+/remix|${REMIX_URL}|g" "$README"
        rm -f "${README}.bak"
        echo "  ✅ README.md atualizado"
        UPDATED=$((UPDATED+1))
    # Substitui placeholder literal
    elif grep -q 'REMIX_URL_PLACEHOLDER\|sua-url-de-remix\|lovable.dev/remix' "$README"; then
        sed -i.bak \
            -e "s|REMIX_URL_PLACEHOLDER|${REMIX_URL}|g" \
            -e "s|sua-url-de-remix|${REMIX_URL}|g" \
            "$README"
        rm -f "${README}.bak"
        echo "  ✅ README.md atualizado (placeholder → URL real)"
        UPDATED=$((UPDATED+1))
    else
        echo "  ⚠️  README.md: nenhum padrão de remix encontrado para substituir"
        echo "     Adicione manualmente: [![Remix no Lovable](https://img.shields.io/badge/Remix-Lovable-blue)](${REMIX_URL})"
    fi
else
    echo "  ⏭️  README.md não encontrado"
fi

# ── 2. src/routes/install.tsx ─────────────────────────────────────────────────
INSTALL_TSX="$REPO_DIR/src/routes/install.tsx"
if [[ -f "$INSTALL_TSX" ]]; then
    if grep -qE 'lovable\.dev/projects/[^"]+/remix|REMIX_URL_PLACEHOLDER|sua-url-de-remix' "$INSTALL_TSX"; then
        sed -i.bak \
            -E "s|https://lovable\\.dev/projects/[^\"']+/remix|${REMIX_URL}|g" \
            -e "s|REMIX_URL_PLACEHOLDER|${REMIX_URL}|g" \
            -e "s|sua-url-de-remix|${REMIX_URL}|g" \
            "$INSTALL_TSX"
        rm -f "${INSTALL_TSX}.bak"
        echo "  ✅ src/routes/install.tsx atualizado"
        UPDATED=$((UPDATED+1))
    else
        echo "  ⚠️  install.tsx: nenhum padrão encontrado"
        echo "     Verifique que o botão de Remix aponta para: ${REMIX_URL}"
    fi
else
    echo "  ⏭️  src/routes/install.tsx não encontrado (Lovable gerencia este arquivo)"
fi

# ── 3. docs/CLIENTE.md ───────────────────────────────────────────────────────
CLIENTE_MD="$REPO_DIR/docs/CLIENTE.md"
if [[ -f "$CLIENTE_MD" ]]; then
    if grep -qE 'lovable\.dev/projects/[^)]+/remix|REMIX_URL_PLACEHOLDER|sua-url-de-remix' "$CLIENTE_MD"; then
        sed -i.bak \
            -E "s|https://lovable\\.dev/projects/[^)\"']+/remix|${REMIX_URL}|g" \
            -e "s|REMIX_URL_PLACEHOLDER|${REMIX_URL}|g" \
            -e "s|sua-url-de-remix|${REMIX_URL}|g" \
            "$CLIENTE_MD"
        rm -f "${CLIENTE_MD}.bak"
        echo "  ✅ docs/CLIENTE.md atualizado"
        UPDATED=$((UPDATED+1))
    else
        echo "  ⚠️  docs/CLIENTE.md: nenhum padrão encontrado para substituir"
        echo "     Passo 1 deve referenciar: ${REMIX_URL}"
    fi
else
    echo "  ⏭️  docs/CLIENTE.md não encontrado"
fi

# ── Resumo ────────────────────────────────────────────────────────────────────
echo ""
if [[ $UPDATED -gt 0 ]]; then
    echo "✅ $UPDATED arquivo(s) atualizado(s) com: $REMIX_URL"
    echo ""
    echo "Próximos passos:"
    echo "  git add README.md docs/CLIENTE.md src/routes/install.tsx"
    echo "  git commit -m 'dist: atualiza URL de Remix do Lovable'"
    echo "  git push"
else
    echo "⚠️  Nenhum arquivo foi atualizado."
    echo "   Verifique se os arquivos contêm placeholders esperados."
fi
