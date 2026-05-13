# Evolution API — WhatsApp Multi-Instância

Integração da Evolution API com o Agente CFO para suporte a múltiplas instâncias WhatsApp.

## Pré-requisitos

- Evolution API rodando (self-hosted ou SaaS) e acessível pela internet
- Variáveis `PANEL_BASE_URL`, `PANEL_TOKEN`, `HOOKS_TOKEN` em `~/.agente-cfo/.env`

## Como configurar (zero SSH)

1. Acesse o painel → Configurações → WhatsApp → Evolution API
2. Informe a URL base e a API key da sua instância Evolution
3. Clique em "Salvar e testar"
4. Em até 30s o daemon detecta a configuração e começa a reconciliar

## Gerenciar instâncias

1. No painel → WhatsApp → Instâncias → "Nova instância"
2. Informe o nome da instância (ex: `vendas`, `suporte`)
3. O daemon cria a instância na Evolution e busca o QR code
4. O QR code aparece no painel — leia com o WhatsApp do celular
5. Após parear: `status=connected`, QR some

## Enviar mensagem via Marcos

```bash
# Marcos usa automaticamente via send_evolution.sh
bash skills/evolution-api/scripts/send_evolution.sh <instance> <numero_e164> <mensagem>
```

## Serviço

```bash
systemctl status cfo-evolution-sync    # status
journalctl -u cfo-evolution-sync -f    # logs em tempo real
systemctl restart cfo-evolution-sync   # forçar sync imediato
```

## Variáveis (todas via painel — nenhuma manual na VPS)

| Variável | Origem |
|----------|--------|
| `EVOLUTION_BASE_URL` | Painel → edge fn `evolution-config-vps` |
| `EVOLUTION_API_KEY` | Painel → edge fn `evolution-config-vps` |
| `EVOLUTION_WEBHOOK_SECRET` | Painel → edge fn `evolution-config-vps` |
