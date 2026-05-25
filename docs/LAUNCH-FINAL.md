# LAUNCH-FINAL.md — Checklist de Lançamento Público

> **Sprint SHIP-1 — 2026-05-25**  
> Checklist completo para o PM antes de divulgar o Agente CFO ao público.  
> Execute na ordem. Itens com **[LOVABLE]** são no dashboard Lovable AI.  
> Itens com **[PM]** são executados localmente pelo PM.

---

## Fase 1: Pré-requisitos de infraestrutura

### GitHub

- [ ] **[PM]** Confirmar que repo `agente-cfo` está público:
  ```bash
  gh repo view MindOpsTeam/agente-cfo --json visibility -q .visibility
  # Esperado: PUBLIC
  ```
- [ ] **[PM]** Confirmar que repo do painel está público:
  ```bash
  gh repo view MindOpsTeam/carteira-do-agente --json visibility -q .visibility
  ```
- [ ] **[PM]** Adicionar topics ao repo:
  ```bash
  gh repo edit MindOpsTeam/agente-cfo \
    --add-topic cfo,ai-agent,anthropic,mcp,whatsapp,brasil,pme,lovable,supabase
  ```

### Supabase Secrets

- [ ] **[PM]** Adicionar `GITHUB_REPORT_ISSUE_TOKEN` no Supabase Dashboard:
  - Dashboard → Settings → Edge Functions → Secrets
  - Valor: Personal Access Token do GitHub com escopo `issues` (e opcionalmente `read:repo`)
  - Criar em: https://github.com/settings/tokens → Generate new token (classic)

- [ ] **[PM]** Aplicar migration `report_issues_log` via lovable_query_sql:
  ```sql
  CREATE TABLE IF NOT EXISTS public.report_issues_log (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    subject text NOT NULL,
    issue_url text,
    created_at timestamptz NOT NULL DEFAULT now()
  );
  CREATE INDEX IF NOT EXISTS idx_report_issues_log_user_created
    ON public.report_issues_log (user_id, created_at DESC);
  ALTER TABLE public.report_issues_log ENABLE ROW LEVEL SECURITY;
  CREATE POLICY "users can insert own reports"
    ON public.report_issues_log FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);
  ```

---

## Fase 2: Configurar template público no Lovable

- [ ] **[LOVABLE]** Acessar https://lovable.dev → Dashboard → projeto `carteira-do-agente`
- [ ] **[LOVABLE]** Marcar projeto como **Published** (botão Publish no canto superior direito)
- [ ] **[LOVABLE]** Marcar visibilidade como **Public**
- [ ] **[LOVABLE]** Ativar **"Allow remixing"** / Public remixable template
- [ ] **[LOVABLE]** Adicionar descrição do projeto:
  ```
  CFO virtual 24/7 para PMEs brasileiras — integra ERP, CRM, cobrança e canais (WhatsApp/Telegram).
  Rode na sua infra via Lovable + Supabase + VPS. 17 integrações plug-and-play.
  ```
- [ ] **[LOVABLE]** Copiar URL de remix público (formato: `https://lovable.dev/projects/XXX/remix`)

---

## Fase 3: Atualizar URL de remix no projeto

- [ ] **[PM]** Criar arquivo com a URL:
  ```bash
  echo "REMIX_URL=https://lovable.dev/projects/SEU-ID-AQUI/remix" \
    > /Users/barboza/agente-cfo/painel-front/install/REMIX_URL.txt
  ```
- [ ] **[PM]** Rodar script de atualização:
  ```bash
  bash /Users/barboza/agente-cfo/painel-front/install/update-remix-url.sh
  # Atualiza README.md, src/routes/install.tsx, docs/CLIENTE.md automaticamente
  ```
- [ ] **[PM]** Verificar que README.md tem o botão remix atualizado:
  ```bash
  grep -i "remix" /Users/barboza/agente-cfo/painel-front/README.md | head -3
  ```

---

## Fase 4: Deploy das features SHIP-1

- [ ] **[LOVABLE]** Disparar prompt `docs/SPRINT-SHIP-1-LOVABLE-PROMPT.md`:
  - Adiciona botão "?" no header global
  - Cria `ReportIssueModal.tsx`
  - Integra com edge fn `report-issue`

- [ ] **[LOVABLE]** Confirmar que edge fn `report-issue` foi deployada:
  - Supabase Dashboard → Edge Functions → verificar `report-issue` na lista

---

## Fase 5: Testes E2E

- [ ] **[PM]** Instalar Playwright (se não instalado):
  ```bash
  cd /Users/barboza/agente-cfo/painel-front
  npm i -D @playwright/test
  npx playwright install chromium
  ```

- [ ] **[PM]** Rodar journey E2E completo:
  ```bash
  BASE_URL=https://carteira-do-agente.lovable.app \
  bash /Users/barboza/agente-cfo/tests/e2e/test_client_full_journey.sh
  # Screenshots em: docs/screenshots/journey/
  ```

- [ ] **[PM]** Gerar vídeo demo (60s):
  ```bash
  bash /Users/barboza/agente-cfo/tests/e2e/generate_demo_video.sh
  # Output: docs/demo.mp4 (ou docs/demo-slideshow.html se ffmpeg ausente)
  ```

- [ ] **[PM]** Rodar todos os smoke tests para garantir zero regressão:
  ```bash
  cd /Users/barboza/agente-cfo
  bash tests/e2e/test_ship1_distribution.sh
  bash tests/e2e/test_chan1_pairing.sh
  bash tests/e2e/test_int2_integrations.sh
  # Todos devem terminar com PASS
  ```

---

## Fase 6: Validação manual de features chave

- [ ] Acessar https://carteira-do-agente.lovable.app/install e verificar que landing carrega
- [ ] Verificar que botão "Remixar no Lovable →" aponta para URL correta
- [ ] Login com admin@agente-cfo.local / CfoAdmin2026! funciona
- [ ] Dashboard carrega sem erros de console
- [ ] /settings → pareamento WhatsApp funciona (CHAN-1)
- [ ] /settings/telegram → formulário de registro automático funciona (CHAN-1)
- [ ] Botão "?" no header abre modal de report
- [ ] Modal report-issue envia issue para GitHub corretamente
  - Testar com: subject "Teste SHIP-1", description "Validação do sistema de report de issues"

---

## Fase 7: Anúncio 🎉

- [ ] **[PM]** Commit final com LAUNCH-FINAL.md atualizado (marcar itens completos)
- [ ] **[PM]** Criar Release no GitHub:
  ```bash
  gh release create v1.0.0 \
    --title "🚀 v1.0.0 — Launch Público" \
    --notes "Agente CFO disponível publicamente para remixing via Lovable. 17 integrações, WhatsApp/Telegram sem SSH, dashboard em tempo real." \
    --repo MindOpsTeam/agente-cfo
  ```
- [ ] **[PM]** Postar vídeo demo (docs/demo.mp4) nas redes
- [ ] **[PM]** Compartilhar URL de remix: https://lovable.dev/projects/XXX/remix

---

## Referência rápida — URLs

| Recurso | URL |
|---------|-----|
| Painel (app) | https://carteira-do-agente.lovable.app |
| Landing | https://carteira-do-agente.lovable.app/install |
| Login | https://carteira-do-agente.lovable.app/login |
| Repo agente-cfo | https://github.com/MindOpsTeam/agente-cfo |
| URL Remix (preencher) | `https://lovable.dev/projects/__PREENCHER__/remix` |

---

## Comandos de diagnóstico (se algo quebrar)

```bash
# Ver smoke tests de todos os sprints
bash tests/e2e/test_chan1_pairing.sh      # Sprint CHAN-1 (WhatsApp/Telegram)
bash tests/e2e/test_int2_integrations.sh  # Sprint INT-2 (17 integrações)
bash tests/e2e/test_ship1_distribution.sh # Sprint SHIP-1 (distribuição)

# Ver status de edge fns
supabase functions list --project-ref <SEU_PROJECT_REF>

# Ver daemons na VPS
ssh cfodebug@<VPS_IP> "systemctl list-units 'cfo-*' --state=running"
```
