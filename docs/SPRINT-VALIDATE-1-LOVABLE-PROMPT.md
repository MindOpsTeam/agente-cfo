# SPRINT-VALIDATE-1-LOVABLE-PROMPT.md

> Texto pronto para PM disparar via lovable_send_prompt.
> Ref: Sprint VALIDATE-1 — Botão "Testar credencial" + feedback inline de 401.

---

## Prompt para Lovable AI

```
Preciso melhorar a página `/integrations` (arquivo `src/routes/_authenticated/integrations.index.tsx`)
com as seguintes mudanças:

### 1. Botão "Testar" com feedback inline em cada card de skill

Cada card de integração já tem o botão "Conectar/Editar". Adicione um segundo botão menor
"Testar" (ícone: Zap ou CheckCircle2) que:

a) Chama a edge fn `integration-credentials-test` com `{ skill_name: spec.slug }` via POST.

b) Mostra spinner enquanto testa.

c) Exibe resultado INLINE abaixo do card (não em toast), persistindo até próxima ação:
   - ✅ "Conexão OK — testado às HH:MM"   → classe text-emerald-600
   - ❌ "Token inválido (401) — clique em Editar pra atualizar"  → classe text-destructive
   - ⚠️ "Escopos faltando — ver instrução no chat"  → classe text-amber-600
   - 🔄 "Sem teste disponível para OAuth — use o fluxo de autorização"  → text-muted-foreground

d) O status salvo em state local por `slug` para todos os cards da página:
   ```typescript
   const [testResults, setTestResults] = useState<Record<string, {
     status: 'ok' | 'invalid' | 'unreachable' | 'unknown';
     detail?: string;
     testedAt: Date;
   }>>({});
   ```

e) O botão "Testar" fica disabled enquanto credentials === null (ainda carregando)
   OU se o status atual for "not_connected" (não tem credencial salva — não há o que testar).
   Tooltip nesse caso: "Salve as credenciais primeiro".

f) Ao lado do StatusPill existente, mostre um badge pequeno com o horário do último teste
   se `testResults[spec.slug]` existir:
   ```tsx
   {testResults[spec.slug] && (
     <span className="text-[10px] text-muted-foreground">
       {format(testResults[spec.slug].testedAt, 'HH:mm')}
     </span>
   )}
   ```

### 2. CredentialsDialog — botão "Testar" habilitado ao criar (não só ao editar)

No arquivo `src/components/integrations/CredentialsDialog.tsx`, o botão "Testar" está
disabled quando `!isExisting`. Mudar a lógica para:
- Se `isExisting` (credencial já existe): testar sem salvar primeiro
- Se `!isExisting` mas campos preenchidos: salvar primeiro, depois testar automaticamente
- Atualizar o title do botão: "Testar conexão" (sempre)

### 3. Mensagem de erro estruturada quando gateway retorna credential_invalid

Quando Marcos responde via chat com um JSON que contém `"error_kind": "credential_invalid"`,
o componente de chat (`src/routes/_authenticated/chat.tsx`) deve detectar e renderizar
uma mensagem especial com:
- Ícone AlertCircle vermelho
- Texto: o campo `message_pt` do JSON
- Link: botão "Corrigir agora →" apontando para `/integrations/<skill>`

Para detectar: parse the `content` field. Se começar com `{` e conter `"error_kind"`,
renderizar o template especial ao invés do texto plain.

Exemplo de content que deve acionar o template:
```json
{"success": false, "error_kind": "credential_invalid", "skill": "asaas",
 "http_status": 401, "fix_url": "/integrations/asaas",
 "message_pt": "Credencial Asaas inválida (HTTP 401). Atualize a API Key em /integrations/asaas e me chame de novo."}
```

### 4. Indicador de saúde no topo da página /integrations

Abaixo do título "Integrações", adicionar um banner compacto se houver integrações com
`last_test_status === 'invalid'` ou `last_test_status === 'unreachable'`:

```tsx
{credentials?.some(c => c.last_test_status === 'invalid' || c.last_test_status === 'unreachable') && (
  <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
    <AlertCircle className="h-4 w-4 shrink-0" />
    <span>
      {credentials.filter(c => ['invalid','unreachable'].includes(c.last_test_status ?? '')).length} integração(ões) com erro de credencial.
      Clique em "Testar" para cada uma.
    </span>
  </div>
)}
```

### Não mudar

- Lógica de OAuth (bling, contaazul, hubspot, mercado-livre, nuvemshop) — mantém fluxo atual
- Lógica de Supabase multi-projeto — mantém rota dedicada /integrations/supabase
- Estrutura do INTEGRATIONS_SPEC — não alterar campos
- A edge fn integration-credentials-test já existe e funciona — não criar nova

### Referência de arquivos a alterar

- `src/routes/_authenticated/integrations.index.tsx` — botão Testar + banner de saúde
- `src/components/integrations/CredentialsDialog.tsx` — habilitar teste ao criar
- `src/routes/_authenticated/chat.tsx` — renderizar credential_invalid como template especial

Usa componentes já existentes: Card, Button, Badge, Tooltip, Loader2, AlertCircle, CheckCircle2 de `@/components/ui/`.
Usa `format` do `date-fns` para HH:mm (já importado em outros componentes).
```

---

## Como disparar

```javascript
// No Lovable, via lovable_send_prompt:
lovable_send_prompt(acima)
```

## Contexto para PM

- edge fn `integration-credentials-test` cobre: omie, tiny, granatum, vhsys, nibo, hubspot, rd-station, piperun, pipedrive, kommo, asaas, iugu (12 skills)
- Skills OAuth (bling, contaazul, mercado-livre, nuvemshop) retornam `status: "unknown"` — exibir mensagem "use o fluxo OAuth"
- Supabase tem página dedicada `/integrations/supabase` — não precisa de botão Testar aqui
- O campo `last_test_status` já existe em `integration_credentials` — populado pela edge fn ao testar
- Após salvar/testar, o `credentials-sync` daemon (3 min) vai puxar e registrar o MCP atualizado

## O que o VPS backend já faz (não mudar)

Quando a credencial é atualizada no painel:
1. `credentials-sync` daemon detecta (a cada 3 min)
2. Sincroniza `~/.openclaw/secrets/<skill>.env`
3. `mcp_manager.register_mcp(skill)` reregistra no openclaw.json
4. Gateway hot-reload — Marcos passa a usar nova credencial automaticamente
