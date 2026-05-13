#!/usr/bin/env bash
source "$HOME/.openclaw/secrets/kommo.env" 2>/dev/null || { echo "ERRO: kommo.env nao encontrado"; exit 1; }
echo -n "Testando Kommo API... "
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $KOMMO_ACCESS_TOKEN" "https://${KOMMO_SUBDOMAIN}.kommo.com/api/v4/account")
[[ "$HTTP" == "200" ]] && echo "OK ($HTTP)" || echo "FALHOU ($HTTP)"
