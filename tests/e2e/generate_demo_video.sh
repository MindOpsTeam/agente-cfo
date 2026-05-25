#!/usr/bin/env bash
# generate_demo_video.sh — SPRINT SHIP-1: Gera vídeo demo 60s via Playwright stop-motion
#
# Navega pelas telas-chave do painel, tira screenshots e gera demo.mp4 (ou GIF).
#
# Uso: bash tests/e2e/generate_demo_video.sh [--base-url <url>]
#
# Requer: npx playwright (Chromium)
# ffmpeg opcional — gera HTML fallback se ausente
#
# Sprint SHIP-1 — 2026-05-25

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEMO_DIR="${REPO_ROOT}/docs/demo-frames"
OUTPUT_MP4="${REPO_ROOT}/docs/demo.mp4"
OUTPUT_GIF="${REPO_ROOT}/docs/demo.gif"
OUTPUT_HTML="${REPO_ROOT}/docs/demo-slideshow.html"

mkdir -p "$DEMO_DIR"

BASE_URL="${BASE_URL:-https://carteira-do-agente.lovable.app}"
HEADLESS="${HEADLESS:-1}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --base-url) BASE_URL="$2"; shift 2 ;;
        --no-headless) HEADLESS=0; shift ;;
        *) shift ;;
    esac
done

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

printf '\n%b╔══════════════════════════════════════════════════╗%b\n' "$CYAN" "$NC"
printf '%b║   SHIP-1 Demo Video Generator — 60s stop-motion  ║%b\n' "$CYAN" "$NC"
printf '%b╚══════════════════════════════════════════════════╝%b\n\n' "$CYAN" "$NC"

printf 'BASE_URL: %s\n' "$BASE_URL"
printf 'Output:   %s\n\n' "$OUTPUT_MP4"

# ── Telas para o demo (8-10 telas key) ────────────────────────────────────────
# Formato: "url|desc|título"
SCREENS=(
    "/install|01-landing|🚀 Landing Pública — Instale em 5 min"
    "/login|02-login|🔐 Login Seguro"
    "/|03-dashboard|📊 Dashboard CFO em Tempo Real"
    "/onboarding|04-onboarding|🧙 Setup em 7 Passos"
    "/integrations|05-integrations|🔌 17 Integrações Plug-and-Play"
    "/chat|06-chat|💬 Chat com Marcos (IA CFO)"
    "/alerts|07-alerts|🔔 Alertas Inteligentes"
    "/settings|08-settings-whatsapp|📱 WhatsApp — Parear sem SSH"
    "/settings/telegram|09-settings-telegram|🤖 Telegram — Webhook Automático"
    "/reports|10-reports|📈 Relatórios Executivos"
)

# ── Playwright script ──────────────────────────────────────────────────────────
PW_SCRIPT=$(mktemp /tmp/_pw_demo_XXXXXX.ts)
DEMO_DIR_ESC=$(printf '%s' "$DEMO_DIR" | sed 's/\\/\\\\/g')

cat > "$PW_SCRIPT" << 'PWEOF'
import { chromium } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE_URL = process.env.DEMO_BASE_URL || 'https://carteira-do-agente.lovable.app';
const DEMO_DIR = process.env.DEMO_DIR || '/tmp/demo-frames';
const HEADLESS = process.env.HEADLESS !== '0';
const WAIT_MS = 3000;  // 3s por tela

const SCREENS: Array<{ path: string; file: string; title: string }> = [
  { path: '/install',       file: '01-landing',           title: '🚀 Landing — Instale em 5 min' },
  { path: '/login',         file: '02-login',             title: '🔐 Login Seguro' },
  { path: '/',              file: '03-dashboard',         title: '📊 Dashboard CFO em Tempo Real' },
  { path: '/onboarding',   file: '04-onboarding',        title: '🧙 Setup em 7 Passos' },
  { path: '/integrations', file: '05-integrations',      title: '🔌 17 Integrações Plug-and-Play' },
  { path: '/chat',         file: '06-chat',              title: '💬 Chat com Marcos (IA CFO)' },
  { path: '/alerts',       file: '07-alerts',            title: '🔔 Alertas Inteligentes' },
  { path: '/settings',     file: '08-whatsapp-pairing',  title: '📱 WhatsApp — Parear sem SSH' },
  { path: '/settings/telegram', file: '09-telegram',    title: '🤖 Telegram — Webhook Auto' },
  { path: '/reports',      file: '10-reports',           title: '📈 Relatórios Executivos' },
];

async function run() {
  const browser = await chromium.launch({ headless: HEADLESS });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    locale: 'pt-BR',
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  page.on('pageerror', () => {});

  const captured: string[] = [];

  for (const screen of SCREENS) {
    try {
      console.log(`  → Capturando: ${screen.file} (${screen.path})`);
      await page.goto(`${BASE_URL}${screen.path}`, {
        waitUntil: 'domcontentloaded',
        timeout: 15000,
      });
      await page.waitForTimeout(WAIT_MS);

      const fname = path.join(DEMO_DIR, `${screen.file}.png`);
      await page.screenshot({ path: fname, fullPage: false });
      captured.push(fname);
      console.log(`    ✓ ${fname}`);
    } catch (e: any) {
      console.log(`    ✗ ${screen.file}: ${e.message?.slice(0, 60)}`);
    }
  }

  await browser.close();

  // Escreve lista de frames capturados para o shell
  const listFile = path.join(DEMO_DIR, '_frames.txt');
  fs.writeFileSync(listFile, captured.join('\n') + '\n');
  console.log(`\nFrames capturados: ${captured.length}/${SCREENS.length}`);
  console.log(`Lista: ${listFile}`);
  process.exit(captured.length === 0 ? 1 : 0);
}

run().catch(e => { console.error(e); process.exit(1); });
PWEOF

# ── Verifica dependências ──────────────────────────────────────────────────────
HAS_PLAYWRIGHT=0
if command -v npx &>/dev/null && npx playwright --version &>/dev/null 2>&1; then
    HAS_PLAYWRIGHT=1
fi

HAS_FFMPEG=0
if command -v ffmpeg &>/dev/null; then
    HAS_FFMPEG=1
fi

printf 'Playwright: %s\n' "$([[ $HAS_PLAYWRIGHT -eq 1 ]] && echo '✓' || echo '✗ não disponível')"
printf 'ffmpeg:     %s\n\n' "$([[ $HAS_FFMPEG -eq 1 ]] && echo '✓' || echo '✗ não disponível (usará HTML fallback)')"

# ── Captura screenshots via Playwright ────────────────────────────────────────
FRAMES_CAPTURED=0

if [[ $HAS_PLAYWRIGHT -eq 1 ]]; then
    printf '%bCapturando frames...%b\n' "$YELLOW" "$NC"

    DEMO_BASE_URL="$BASE_URL" DEMO_DIR="$DEMO_DIR" HEADLESS="$HEADLESS" \
    node -e "
const {chromium} = require('@playwright/test');
const path = require('path');
const fs = require('fs');
" 2>/dev/null || true  # teste rápido de disponibilidade do módulo

    # Roda via tsx ou esbuild
    if command -v tsx &>/dev/null; then
        DEMO_BASE_URL="$BASE_URL" DEMO_DIR="$DEMO_DIR" HEADLESS="$HEADLESS" \
        tsx "$PW_SCRIPT" 2>&1 && PW_OK=1 || PW_OK=0
    elif command -v ts-node &>/dev/null; then
        DEMO_BASE_URL="$BASE_URL" DEMO_DIR="$DEMO_DIR" HEADLESS="$HEADLESS" \
        ts-node "$PW_SCRIPT" 2>&1 && PW_OK=1 || PW_OK=0
    else
        # esbuild transpile + node
        JS_SCRIPT="${PW_SCRIPT%.ts}.js"
        npx esbuild "$PW_SCRIPT" --bundle --platform=node --target=node18 \
            --external:@playwright/test --external:playwright \
            --outfile="$JS_SCRIPT" 2>/dev/null
        DEMO_BASE_URL="$BASE_URL" DEMO_DIR="$DEMO_DIR" HEADLESS="$HEADLESS" \
        node "$JS_SCRIPT" 2>&1 && PW_OK=1 || PW_OK=0
        rm -f "$JS_SCRIPT"
    fi

    FRAMES_CAPTURED=$(ls "$DEMO_DIR"/*.png 2>/dev/null | wc -l | tr -d ' ' || echo 0)
    printf '\n%b%d frames capturados%b\n' "$GREEN" "$FRAMES_CAPTURED" "$NC"
else
    printf '%bPlaywright ausente — usando screenshots existentes...%b\n' "$YELLOW" "$NC"
    # Usa screenshots da journey se existirem
    EXISTING="${REPO_ROOT}/docs/screenshots"
    if ls "$EXISTING"/*.png &>/dev/null 2>&1; then
        cp "$EXISTING"/*.png "$DEMO_DIR/" 2>/dev/null || true
        FRAMES_CAPTURED=$(ls "$DEMO_DIR"/*.png 2>/dev/null | wc -l | tr -d ' ' || echo 0)
        printf '  Copiados %d screenshots existentes de docs/screenshots/\n' "$FRAMES_CAPTURED"
    else
        printf '  %bNenhum screenshot disponível%b\n' "$RED" "$NC"
        FRAMES_CAPTURED=0
    fi
fi

rm -f "$PW_SCRIPT"

# ── Monta vídeo ou fallback ────────────────────────────────────────────────────
if [[ $FRAMES_CAPTURED -gt 0 ]]; then

    # Renomeia frames para sequência numerada que ffmpeg espera
    FFMPEG_DIR="${DEMO_DIR}/ffmpeg_sequence"
    mkdir -p "$FFMPEG_DIR"
    i=0
    for f in $(ls "$DEMO_DIR"/*.png 2>/dev/null | sort); do
        cp "$f" "$FFMPEG_DIR/$(printf 'frame-%03d.png' $i)"
        i=$((i+1))
    done

    if [[ $HAS_FFMPEG -eq 1 ]]; then
        printf '\n%bGerando demo.mp4 com ffmpeg...%b\n' "$YELLOW" "$NC"

        # 1 frame a cada 6 segundos → vídeo de ~60s com 10 telas
        ffmpeg -y \
            -framerate "1/6" \
            -pattern_type glob \
            -i "${FFMPEG_DIR}/frame-*.png" \
            -c:v libx264 \
            -pix_fmt yuv420p \
            -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" \
            -preset slow \
            -crf 22 \
            "$OUTPUT_MP4" 2>/dev/null

        if [[ -f "$OUTPUT_MP4" ]]; then
            SIZE=$(du -sh "$OUTPUT_MP4" | cut -f1)
            printf '%b✓ demo.mp4 gerado: %s (%s)%b\n' "$GREEN" "$OUTPUT_MP4" "$SIZE" "$NC"
        fi

        # Também gera GIF (menor, para README/preview)
        printf '%bGerando demo.gif (preview)...%b\n' "$YELLOW" "$NC"
        ffmpeg -y \
            -framerate "1/6" \
            -pattern_type glob \
            -i "${FFMPEG_DIR}/frame-*.png" \
            -vf "fps=1,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
            "$OUTPUT_GIF" 2>/dev/null || true

        if [[ -f "$OUTPUT_GIF" ]]; then
            SIZE_GIF=$(du -sh "$OUTPUT_GIF" | cut -f1)
            printf '%b✓ demo.gif gerado: %s (%s)%b\n' "$GREEN" "$OUTPUT_GIF" "$SIZE_GIF" "$NC"
        fi
    else
        printf '\n%bffmpeg não disponível — gerando HTML slideshow...%b\n' "$YELLOW" "$NC"

        # Gera HTML slideshow como fallback
        cat > "$OUTPUT_HTML" << HTMLEOF
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Agente CFO — Demo</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #0f172a; color: white; font-family: system-ui, sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; }
    h1 { font-size: 1.5rem; margin-bottom: 1rem; color: #38bdf8; }
    #slide { max-width: 1280px; width: 100%; }
    #slide img { width: 100%; border-radius: 8px; border: 1px solid #1e293b; }
    #caption { margin-top: 0.5rem; text-align: center; color: #94a3b8; font-size: 0.9rem; }
    #controls { margin-top: 1rem; display: flex; gap: 1rem; align-items: center; }
    button { background: #1e40af; color: white; border: none; padding: 0.5rem 1.5rem; border-radius: 6px; cursor: pointer; font-size: 1rem; }
    button:hover { background: #2563eb; }
    #counter { color: #64748b; font-size: 0.9rem; min-width: 5rem; text-align: center; }
    #progress { width: 100%; max-width: 1280px; height: 3px; background: #1e293b; margin-top: 0.5rem; }
    #progress-bar { height: 100%; background: #38bdf8; transition: width 0.3s; }
  </style>
</head>
<body>
  <h1>🤖 Agente CFO — Demo (${FRAMES_CAPTURED} telas)</h1>
  <div id="slide"><img id="img" src="" alt="demo"></div>
  <div id="caption"></div>
  <div id="progress"><div id="progress-bar"></div></div>
  <div id="controls">
    <button onclick="prev()">← Anterior</button>
    <span id="counter">1 / ${FRAMES_CAPTURED}</span>
    <button onclick="next()">Próximo →</button>
    <button onclick="toggleAuto()">⏵ Auto</button>
  </div>
  <script>
    const frames = [
HTMLEOF
        # Injeta frames como data URIs ou caminhos relativos
        for f in $(ls "$DEMO_DIR"/*.png 2>/dev/null | sort); do
            name=$(basename "$f" .png)
            printf '      {src: "./demo-frames/%s.png", title: "%s"},\n' "$name" "$name" >> "$OUTPUT_HTML"
        done
        cat >> "$OUTPUT_HTML" << 'HTMLEOF2'
    ];
    let current = 0, timer = null;
    function show(i) {
      current = (i + frames.length) % frames.length;
      document.getElementById('img').src = frames[current].src;
      document.getElementById('caption').textContent = frames[current].title;
      document.getElementById('counter').textContent = (current + 1) + ' / ' + frames.length;
      document.getElementById('progress-bar').style.width = ((current + 1) / frames.length * 100) + '%';
    }
    function prev() { show(current - 1); }
    function next() { show(current + 1); }
    function toggleAuto() {
      if (timer) { clearInterval(timer); timer = null; }
      else { timer = setInterval(() => show(current + 1), 6000); }
    }
    show(0);
  </script>
</body>
</html>
HTMLEOF2

        printf '%b✓ HTML slideshow gerado: %s%b\n' "$GREEN" "$OUTPUT_HTML" "$NC"
        printf '  Instale ffmpeg para gerar MP4: brew install ffmpeg\n'
        printf '  Depois rode: ffmpeg -framerate 1/6 -pattern_type glob -i "docs/demo-frames/frame-*.png" -c:v libx264 -pix_fmt yuv420p docs/demo.mp4\n'
    fi
fi

# ── Resumo ────────────────────────────────────────────────────────────────────
printf '\n%b══════════════════════════════════════%b\n' "$YELLOW" "$NC"
printf 'Demo generator: %b%d frames%b' "$GREEN" "$FRAMES_CAPTURED" "$NC"
[[ -f "$OUTPUT_MP4" ]] && printf ' | %bdemo.mp4 ✓%b' "$GREEN" "$NC"
[[ -f "$OUTPUT_GIF" ]] && printf ' | %bdemo.gif ✓%b' "$GREEN" "$NC"
[[ -f "$OUTPUT_HTML" ]] && printf ' | %bHTML fallback ✓%b' "$GREEN" "$NC"
printf '\n%b══════════════════════════════════════%b\n' "$YELLOW" "$NC"

[[ $FRAMES_CAPTURED -gt 0 ]] && exit 0 || exit 1
