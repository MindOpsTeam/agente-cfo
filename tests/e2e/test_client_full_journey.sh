#!/usr/bin/env bash
# test_client_full_journey.sh — SPRINT SHIP-1: Journey E2E cliente novo via Playwright
#
# Navega por todas as telas chave do painel, tira screenshots e valida renderização.
# Não interage com VPS real — só verifica que as páginas carregam corretamente.
#
# Uso:
#   bash tests/e2e/test_client_full_journey.sh [--base-url <url>] [--headless]
#
# Variáveis de ambiente:
#   BASE_URL     URL base do painel (default: https://carteira-do-agente.lovable.app)
#   ADMIN_EMAIL  Email do admin (default: admin@agente-cfo.local)
#   ADMIN_PASS   Senha do admin (default: CfoAdmin2026!)
#   HEADLESS     1 para headless (default: 1)
#
# Requer: Node.js + npx playwright
# Sprint SHIP-1 — 2026-05-25

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCREENSHOTS_DIR="${REPO_ROOT}/docs/screenshots/journey"
mkdir -p "$SCREENSHOTS_DIR"

# ── Configuração ──────────────────────────────────────────────────────────────
BASE_URL="${BASE_URL:-https://carteira-do-agente.lovable.app}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@agente-cfo.local}"
ADMIN_PASS="${ADMIN_PASS:-CfoAdmin2026!}"
HEADLESS="${HEADLESS:-1}"

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --base-url) BASE_URL="$2"; shift 2 ;;
        --headless) HEADLESS=1; shift ;;
        --no-headless) HEADLESS=0; shift ;;
        *) shift ;;
    esac
done

# ── Cores ─────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

PASS=0; FAIL=0; TOTAL=0

_check() {
    local desc="$1" result="$2" detail="${3:-}"
    TOTAL=$((TOTAL+1))
    if [[ "$result" == "pass" ]]; then
        PASS=$((PASS+1)); printf '  %b✓%b %s\n' "$GREEN" "$NC" "$desc"
    else
        FAIL=$((FAIL+1)); printf '  %b✗%b %s\n' "$RED" "$NC" "$desc"
        [[ -n "$detail" ]] && printf '      %b→ %s%b\n' "$YELLOW" "$detail" "$NC"
    fi
}

_section() { printf '\n%b== %s ==%b\n' "$CYAN" "$1" "$NC"; }

printf '\n%b╔══════════════════════════════════════════════════════╗%b\n' "$CYAN" "$NC"
printf '%b║   SHIP-1 Journey E2E — Cliente Novo via Playwright   ║%b\n' "$CYAN" "$NC"
printf '%b╚══════════════════════════════════════════════════════╝%b\n\n' "$CYAN" "$NC"

# ── Pré-requisitos ─────────────────────────────────────────────────────────────
_section "PRÉ-REQUISITOS"

if command -v npx &>/dev/null && npx playwright --version &>/dev/null 2>&1; then
    PW_VERSION=$(npx playwright --version 2>/dev/null | head -1)
    _check "Playwright disponível ($PW_VERSION)" "pass"
    HAS_PLAYWRIGHT=1
else
    _check "Playwright disponível" "fail" "instale: npm i -D @playwright/test && npx playwright install chromium"
    HAS_PLAYWRIGHT=0
fi

# ── Script Playwright inline ───────────────────────────────────────────────────
# Gera um script TS temporário e o executa
PW_SCRIPT=$(mktemp /tmp/_pw_journey_XXXXXX.ts)
SCREENSHOTS_DIR_ESC=$(printf '%s' "$SCREENSHOTS_DIR" | sed 's/\\/\\\\/g')
BASE_URL_ESC=$(printf '%s' "$BASE_URL" | sed 's/\//\\\//g')

cat > "$PW_SCRIPT" << PWEOF
import { chromium, Browser, Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = '${BASE_URL}';
const ADMIN_EMAIL = '${ADMIN_EMAIL}';
const ADMIN_PASS = '${ADMIN_PASS}';
const SCREENSHOTS_DIR = '${SCREENSHOTS_DIR_ESC}';
const HEADLESS = ${HEADLESS} === 1;

interface StepResult {
  step: number;
  desc: string;
  ok: boolean;
  detail?: string;
}

const results: StepResult[] = [];

function log(step: number, desc: string, ok: boolean, detail?: string) {
  const icon = ok ? '✓' : '✗';
  console.log(\`  \${icon} Step \${step}: \${desc}\${detail ? ' — ' + detail : ''}\`);
  results.push({ step, desc, ok, detail });
}

async function screenshot(page: Page, step: number, desc: string) {
  const fname = path.join(SCREENSHOTS_DIR, \`\${String(step).padStart(2,'0')}-\${desc}.png\`);
  try {
    await page.screenshot({ path: fname, fullPage: false });
    console.log(\`    📸 screenshot: \${fname}\`);
  } catch (e) {
    console.log(\`    ⚠ screenshot failed: \${e}\`);
  }
}

async function waitAndCheck(page: Page, selector: string, label: string): Promise<boolean> {
  try {
    await page.waitForSelector(selector, { timeout: 10000 });
    return true;
  } catch {
    return false;
  }
}

async function run() {
  const browser: Browser = await chromium.launch({ headless: HEADLESS });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    locale: 'pt-BR',
  });
  const page = await context.newPage();

  // Ignora erros de console não críticos
  page.on('pageerror', () => {});

  try {
    // ── STEP 1: Landing /install ─────────────────────────────────────────────
    console.log('\\n== STEP 1: Landing /install ==');
    try {
      await page.goto(\`\${BASE_URL}/install\`, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(2000);
      await screenshot(page, 1, 'landing-install');

      // Verifica CTA "Remixar" presente
      const hasRemix = await waitAndCheck(page, 'a[href*="lovable"], button:has-text("Remixar"), [data-testid="remix-cta"], a:has-text("Remix")', 'CTA Remix');
      // Verifica que a página carregou (tem algum conteúdo)
      const hasContent = await waitAndCheck(page, 'main, .container, [class*="card"], h1, h2', 'conteúdo');
      log(1, 'Landing /install carrega', hasContent, hasContent ? undefined : 'sem conteúdo detectado');
      log(2, 'CTA "Remixar no Lovable" presente', hasRemix, hasRemix ? undefined : 'elemento não encontrado (pode estar com texto diferente)');
    } catch (e: any) {
      log(1, 'Landing /install carrega', false, e.message?.slice(0, 80));
      log(2, 'CTA "Remixar" presente', false, 'página não carregou');
    }

    // ── STEP 3: /login ───────────────────────────────────────────────────────
    console.log('\\n== STEP 3: Login ==');
    try {
      await page.goto(\`\${BASE_URL}/login\`, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(1500);
      await screenshot(page, 3, 'login');

      const hasForm = await waitAndCheck(page, 'input[type="email"], input[name="email"], [placeholder*="email"], [placeholder*="e-mail"]', 'form email');
      log(3, '/login carrega com formulário de email', hasForm, hasForm ? undefined : 'input email não encontrado');

      // Tenta login se form presente
      if (hasForm) {
        try {
          await page.fill('input[type="email"], input[name="email"]', ADMIN_EMAIL);
          const passInput = await page.$('input[type="password"]');
          if (passInput) {
            await passInput.fill(ADMIN_PASS);
            await page.keyboard.press('Enter');
            await page.waitForTimeout(3000);
            await screenshot(page, 4, 'after-login');
            const url = page.url();
            const loggedIn = !url.includes('/login') && !url.includes('/auth');
            log(4, 'Login com admin@agente-cfo.local bem-sucedido', loggedIn,
              loggedIn ? undefined : \`ainda em: \${url}\`);
          } else {
            log(4, 'Login executado', false, 'campo senha não encontrado');
          }
        } catch (e: any) {
          log(4, 'Login executado', false, e.message?.slice(0, 80));
        }
      } else {
        log(4, 'Login com admin', false, 'form não disponível');
      }
    } catch (e: any) {
      log(3, '/login carrega', false, e.message?.slice(0, 80));
      log(4, 'Login admin', false, 'página falhou');
    }

    // ── STEP 5: Dashboard ────────────────────────────────────────────────────
    console.log('\\n== STEP 5: Dashboard ==');
    try {
      await page.goto(\`\${BASE_URL}/\`, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(2000);
      await screenshot(page, 5, 'dashboard');
      const hasDash = await waitAndCheck(page, 'main, [class*="dashboard"], [class*="card"], nav', 'dashboard content');
      log(5, 'Dashboard / carrega', hasDash, hasDash ? undefined : 'sem conteúdo');
    } catch (e: any) {
      log(5, 'Dashboard carrega', false, e.message?.slice(0, 80));
    }

    // ── STEP 6: /onboarding ──────────────────────────────────────────────────
    console.log('\\n== STEP 6: Onboarding ==');
    try {
      await page.goto(\`\${BASE_URL}/onboarding\`, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(2000);
      await screenshot(page, 6, 'onboarding');
      const hasWizard = await waitAndCheck(page, '[class*="step"], [class*="wizard"], [class*="card"], button, h1, h2, h3', 'wizard');
      log(6, '/onboarding wizard step 1 carrega', hasWizard, hasWizard ? undefined : 'wizard não encontrado');
    } catch (e: any) {
      log(6, '/onboarding carrega', false, e.message?.slice(0, 80));
    }

    // ── STEP 7: /integrations ────────────────────────────────────────────────
    console.log('\\n== STEP 7: Integrations ==');
    try {
      await page.goto(\`\${BASE_URL}/integrations\`, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(2000);
      await screenshot(page, 7, 'integrations');
      // Verifica cards de integração
      const cards = await page.$$('[class*="card"], [class*="integration"], [class*="grid"] > *');
      const hasCards = cards.length >= 3;
      log(7, '/integrations grid de integrações carrega', hasCards,
        hasCards ? undefined : \`apenas \${cards.length} elemento(s) encontrado(s)\`);
    } catch (e: any) {
      log(7, '/integrations carrega', false, e.message?.slice(0, 80));
    }

    // ── STEP 8: /chat ────────────────────────────────────────────────────────
    console.log('\\n== STEP 8: Chat ==');
    try {
      await page.goto(\`\${BASE_URL}/chat\`, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(2000);
      await screenshot(page, 8, 'chat');
      const hasChat = await waitAndCheck(page, 'main, [class*="chat"], [class*="message"], input, textarea', 'chat content');
      log(8, '/chat carrega', hasChat, hasChat ? undefined : 'sem conteúdo detectado');
    } catch (e: any) {
      log(8, '/chat carrega', false, e.message?.slice(0, 80));
    }

    // ── STEP 9: /alerts ──────────────────────────────────────────────────────
    console.log('\\n== STEP 9: Alerts ==');
    try {
      await page.goto(\`\${BASE_URL}/alerts\`, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(2000);
      await screenshot(page, 9, 'alerts');
      const hasAlerts = await waitAndCheck(page, 'main, [class*="alert"], [class*="card"], button, h1', 'alerts content');
      log(9, '/alerts carrega', hasAlerts, hasAlerts ? undefined : 'sem conteúdo');
    } catch (e: any) {
      log(9, '/alerts carrega', false, e.message?.slice(0, 80));
    }

    // ── STEP 10: /settings (WhatsApp) ────────────────────────────────────────
    console.log('\\n== STEP 10: Settings WhatsApp (CHAN-1) ==');
    try {
      await page.goto(\`\${BASE_URL}/settings\`, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(2000);
      await screenshot(page, 10, 'settings-whatsapp');

      // Verifica presença de elemento relacionado a WA/pairing
      const hasWA = await waitAndCheck(page,
        'button:has-text("Parear"), [data-testid*="pair"], [class*="whatsapp"], h1:has-text("WhatsApp"), h2:has-text("WhatsApp"), [class*="instance"]',
        'whatsapp pair button');
      log(10, '/settings — botão Parear instância WhatsApp presente (CHAN-1)', hasWA,
        hasWA ? undefined : 'elemento de pareamento não encontrado (CHAN-1 pode estar em sub-rota)');
    } catch (e: any) {
      log(10, '/settings WhatsApp carrega', false, e.message?.slice(0, 80));
    }

    // ── STEP 11: /settings/telegram ─────────────────────────────────────────
    console.log('\\n== STEP 11: Settings Telegram (CHAN-1) ==');
    try {
      // Tenta rota específica primeiro
      for (const route of ['/settings/telegram', '/settings/sistema', '/settings']) {
        try {
          await page.goto(\`\${BASE_URL}\${route}\`, { waitUntil: 'domcontentloaded', timeout: 15000 });
          await page.waitForTimeout(1500);
          const hasTG = await waitAndCheck(page,
            'input[placeholder*="token"], input[placeholder*="Token"], [data-testid*="telegram"], [class*="telegram"], h1:has-text("Telegram"), h2:has-text("Telegram")',
            'telegram form');
          if (hasTG) {
            await screenshot(page, 11, 'settings-telegram');
            log(11, \`\${route} — formulário Telegram presente (CHAN-1)\`, true);
            break;
          }
          if (route === '/settings') {
            await screenshot(page, 11, 'settings-telegram');
            log(11, '/settings/telegram — formulário registro automático', hasTG,
              hasTG ? undefined : 'input bot_token não encontrado');
          }
        } catch {}
      }
    } catch (e: any) {
      log(11, '/settings/telegram carrega', false, e.message?.slice(0, 80));
    }

  } catch (e: any) {
    console.error('ERRO FATAL no Playwright:', e.message);
  } finally {
    await browser.close();
  }

  // ── Saída ─────────────────────────────────────────────────────────────────
  const passed = results.filter(r => r.ok).length;
  const failed = results.filter(r => !r.ok).length;

  console.log(\`\\n══════════════════════════════════════\`);
  console.log(\`SHIP-1 Journey: \${passed}/\${results.length} PASS\${failed > 0 ? ' | ' + failed + ' FAIL' : ''}\`);
  console.log(\`Screenshots em: \${SCREENSHOTS_DIR}\`);
  console.log(\`══════════════════════════════════════\`);

  // Escreve resultado JSON para consumo externo
  const resultPath = path.join(SCREENSHOTS_DIR, '_journey_result.json');
  fs.writeFileSync(resultPath, JSON.stringify({ passed, failed, total: results.length, results }, null, 2));

  process.exit(failed > 0 ? 1 : 0);
}

run().catch(e => { console.error(e); process.exit(1); });
PWEOF

# ── Execução ──────────────────────────────────────────────────────────────────
if [[ "$HAS_PLAYWRIGHT" == "1" ]]; then
    _section "EXECUTANDO JOURNEY (Playwright)"

    # Verifica se Chromium está instalado
    if ! npx playwright install chromium --dry-run &>/dev/null 2>&1; then
        printf '  %bInstalando Chromium...%b\n' "$YELLOW" "$NC"
        npx playwright install chromium 2>/dev/null || true
    fi

    printf '  BASE_URL: %s\n' "$BASE_URL"
    printf '  HEADLESS: %s\n' "$HEADLESS"
    printf '  SCREENSHOTS: %s\n' "$SCREENSHOTS_DIR"
    echo ""

    # Roda o script Playwright direto com node (ts-node ou tsx se disponível)
    if command -v tsx &>/dev/null; then
        tsx "$PW_SCRIPT" 2>&1
        PW_EXIT=$?
    elif command -v ts-node &>/dev/null; then
        ts-node "$PW_SCRIPT" 2>&1
        PW_EXIT=$?
    else
        # Transpila com npx e roda
        JS_SCRIPT="${PW_SCRIPT%.ts}.js"
        npx esbuild "$PW_SCRIPT" --bundle --platform=node --target=node18 \
            --external:@playwright/test --external:playwright \
            --outfile="$JS_SCRIPT" 2>/dev/null && \
        node "$JS_SCRIPT" 2>&1 && PW_EXIT=0 || PW_EXIT=$?
        rm -f "$JS_SCRIPT"
    fi

    if [[ $PW_EXIT -eq 0 ]]; then
        _check "Journey Playwright concluído sem falhas" "pass"
    else
        _check "Journey Playwright" "fail" "exit code $PW_EXIT — verifique screenshots em $SCREENSHOTS_DIR"
    fi
else
    _section "PLAYWRIGHT AUSENTE — VERIFICAÇÕES ESTÁTICAS"
    printf '  %bPlaywright não disponível. Verificando artefatos estáticos...%b\n\n' "$YELLOW" "$NC"

    # Verificações estáticas quando Playwright não está disponível
    # 1. Rotas existem no código
    ROUTES_DIR="${REPO_ROOT}/painel-front/src/routes"

    _check "Rota /install existe" "$([ -f "$ROUTES_DIR/install.tsx" ] && echo pass || echo fail)"
    _check "Rota /login existe" "$([ -f "$ROUTES_DIR/login.tsx" ] && echo pass || echo fail)"
    _check "Rota /onboarding existe" "$([ -f "$ROUTES_DIR/onboarding.tsx" ] && echo pass || echo fail)"
    _check "Rota /integrations existe" "$([ -f "$ROUTES_DIR/_authenticated/integrations.index.tsx" ] && echo pass || echo fail)"
    _check "Rota /chat existe" "$([ -f "$ROUTES_DIR/_authenticated/chat.tsx" ] && echo pass || echo fail)"
    _check "Rota /alerts existe" "$([ -f "$ROUTES_DIR/_authenticated/alerts.tsx" ] && echo pass || echo fail)"
    _check "Rota /settings existe" "$([ -f "$ROUTES_DIR/_authenticated/settings.tsx" ] && echo pass || echo fail)"
    _check "Rota /settings_.telegram existe" "$([ -f "$ROUTES_DIR/_authenticated/settings_.telegram.tsx" ] && echo pass || echo fail)"

    # 2. CHAN-1 features no código
    if grep -q "Parear\|pair\|whatsapp_pair" "$ROUTES_DIR/onboarding.tsx" 2>/dev/null; then
        _check "CHAN-1: feature 'Parear WhatsApp' presente" "pass"
    else
        _check "CHAN-1: feature 'Parear WhatsApp' presente" "fail" "texto 'Parear' não encontrado em onboarding.tsx"
    fi

    if grep -q "bot_token\|webhook_secret\|telegram" "$ROUTES_DIR/_authenticated/settings_.telegram.tsx" 2>/dev/null; then
        _check "CHAN-1: formulário Telegram automático presente" "pass"
    else
        _check "CHAN-1: formulário Telegram automático presente" "fail"
    fi

    # 3. Screenshots anteriores existem
    if ls "$SCREENSHOTS_DIR/../"*.png &>/dev/null 2>&1 || ls "$SCREENSHOTS_DIR/"*.png &>/dev/null 2>&1; then
        _check "Screenshots existem em docs/screenshots/" "pass"
    else
        _check "Screenshots existem em docs/screenshots/" "fail" "execute com Playwright para gerar"
    fi
fi

rm -f "$PW_SCRIPT"

# ── Resumo ────────────────────────────────────────────────────────────────────
printf '\n%b══════════════════════════════════════%b\n' "$YELLOW" "$NC"
printf 'SHIP-1 Journey Smoke: %b%d/%d PASS%b' "$GREEN" "$PASS" "$TOTAL" "$NC"
[[ $FAIL -gt 0 ]] && printf ' | %b%d FAIL%b' "$RED" "$FAIL" "$NC"
printf '\n%b══════════════════════════════════════%b\n' "$YELLOW" "$NC"

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
