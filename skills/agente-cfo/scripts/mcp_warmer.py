#!/usr/bin/env python3
"""
mcp_warmer.py — Daemon de pre-warm dos MCP servers.

Sprint 36 — redução de cold-start: cada MCP server é "aquecido" periodicamente
executando um handshake initialize + tools/list. Para servidores npx, isso
garante que o cache npm esteja quente. Para servidores Python locais, garante
que o processo sobe corretamente.

Loop a cada MCP_WARMER_INTERVAL_MIN (default: 10 min).
Para cada MCP server em openclaw.json:
  1. Spawna o servidor
  2. Envia initialize + tools/list
  3. Registra tempo de resposta
  4. Mata o processo

Logs: ~/.agente-cfo/logs/mcp-warmer.log
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ENV_FILE    = Path.home() / ".agente-cfo" / ".env"
LOG_FILE    = Path.home() / ".agente-cfo" / "logs" / "mcp-warmer.log"
CONFIG_FILE = Path.home() / ".openclaw" / "openclaw.json"

INTERVAL_MINUTES = int(os.environ.get("MCP_WARMER_INTERVAL_MIN", "10"))
INTERVAL_SECONDS = INTERVAL_MINUTES * 60

# Timeout individual por MCP server (segundos)
WARMUP_TIMEOUT_S = int(os.environ.get("MCP_WARMER_TIMEOUT_S", "30"))

# JSON-RPC messages para inicialização + list tools
_INIT_MSG = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "warmer", "version": "1.0"},
    },
}) + "\n"

# notifications/initialized é obrigatório antes de tools/list no protocolo MCP
_INITIALIZED_NOTIF = json.dumps({
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
}) + "\n"

_TOOLS_LIST_MSG = json.dumps({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
}) + "\n"

_STDIN = (_INIT_MSG + _INITIALIZED_NOTIF + _TOOLS_LIST_MSG).encode("utf-8")


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── Env loader ────────────────────────────────────────────────────────────────

def load_env() -> None:
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE) as f:
        for raw in f:
            raw = raw.strip()
            if raw and not raw.startswith("#") and "=" in raw:
                k, _, v = raw.partition("=")
                os.environ.setdefault(k.strip(), v.strip())


# ── Config reader ─────────────────────────────────────────────────────────────

def read_mcp_servers() -> dict:
    """Lê openclaw.json e retorna o dict mcp.servers."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text())
        return data.get("mcp", {}).get("servers", {})
    except Exception as e:
        log(f"[config] Erro ao ler openclaw.json: {e}")
        return {}


# ── Warmer individual ─────────────────────────────────────────────────────────

def warm_server(name: str, config: dict) -> dict:
    """
    Spawna o MCP server, envia initialize + tools/list, retorna métricas.
    { name, status: "ok"|"timeout"|"error", tools: N, elapsed_ms: N, error?: str }
    """
    command = config.get("command", "")
    args = config.get("args", [])
    env_overrides = config.get("env", {})

    if not command:
        return {"name": name, "status": "error", "tools": 0, "elapsed_ms": 0, "error": "sem command"}

    # Monta ambiente do processo
    proc_env = {**os.environ}
    for k, v in env_overrides.items():
        if v and not str(v).startswith("__OPENCLAW"):  # ignora redactados
            proc_env[k] = str(v)

    cmd = [command] + [str(a) for a in args]
    t0 = time.monotonic()

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=proc_env,
        )

        try:
            # Escreve stdin e fecha — servidor lê os 2 requests e termina quando stdin fecha
            proc.stdin.write(_STDIN)
            proc.stdin.close()

            # Coleta stdout com timeout
            deadline = time.monotonic() + WARMUP_TIMEOUT_S
            output_lines: list[str] = []
            assert proc.stdout is not None
            while time.monotonic() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break
                output_lines.append(line.decode("utf-8", errors="replace").strip())
                # Para após receber resposta ao tools/list (id=2)
                try:
                    obj = json.loads(output_lines[-1])
                    if obj.get("id") == 2:
                        break
                except Exception:
                    pass

            proc.kill()
            proc.wait()
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            return {"name": name, "status": "timeout", "tools": 0, "elapsed_ms": elapsed_ms}

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        # Conta tools na resposta
        tools_count = 0
        for line in output_lines:
            try:
                obj = json.loads(line)
                if obj.get("id") == 2:
                    tools_count = len(obj.get("result", {}).get("tools", []))
                    break
            except Exception:
                pass

        return {
            "name": name,
            "status": "ok",
            "tools": tools_count,
            "elapsed_ms": elapsed_ms,
        }

    except FileNotFoundError as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {"name": name, "status": "error", "tools": 0, "elapsed_ms": elapsed_ms,
                "error": f"comando não encontrado: {command}"}
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {"name": name, "status": "error", "tools": 0, "elapsed_ms": elapsed_ms,
                "error": str(e)[:120]}


# ── Ciclo de warm ─────────────────────────────────────────────────────────────

def warm_cycle() -> None:
    """Aquece todos os MCP servers ativos."""
    servers = read_mcp_servers()
    if not servers:
        log("[warmer] Nenhum MCP server configurado — skip")
        return

    log(f"[warmer] Aquecendo {len(servers)} MCP server(s)...")
    results = []

    for name, config in servers.items():
        log(f"[warmer] → {name} ({config.get('command')} {' '.join(str(a) for a in config.get('args', []))[:60]})")
        result = warm_server(name, config)
        results.append(result)

        status_sym = "✓" if result["status"] == "ok" else ("⏱" if result["status"] == "timeout" else "✗")
        tools_str = f"{result['tools']} tools" if result["tools"] else ""
        err_str = f" — {result.get('error', '')}" if result.get("error") else ""
        log(f"  {status_sym} {name}: {result['status']} {tools_str} ({result['elapsed_ms']}ms){err_str}")

    ok_count = sum(1 for r in results if r["status"] == "ok")
    total_ms = sum(r["elapsed_ms"] for r in results)
    avg_ms = total_ms // len(results) if results else 0
    log(f"[warmer] Ciclo concluído: {ok_count}/{len(results)} OK | avg {avg_ms}ms | total {total_ms}ms")


# ── Pre-install npm packages ──────────────────────────────────────────────────

# Pacotes npm para instalar globalmente (cache permanente, sem --prefer-offline issue)
NPM_GLOBAL_PACKAGES = [
    "@supabase/mcp-server-supabase@latest",
]


def ensure_npm_packages() -> None:
    """Garante que pacotes npm comuns dos MCP servers estão instalados globalmente."""
    for pkg in NPM_GLOBAL_PACKAGES:
        pkg_name = pkg.split("@")[0].lstrip("@").replace("/", "-")
        log(f"[npm] Verificando {pkg}...")
        try:
            result = subprocess.run(
                ["npm", "list", "-g", "--depth=0", pkg.split("@")[0]],
                capture_output=True, text=True, timeout=30,
            )
            if "empty" not in result.stdout and "not found" not in result.stderr:
                log(f"  ✓ {pkg} já instalado")
                continue
            # Instala
            log(f"  → instalando {pkg}...")
            inst = subprocess.run(
                ["npm", "install", "-g", "--prefer-offline", pkg],
                capture_output=True, text=True, timeout=120,
            )
            if inst.returncode == 0:
                log(f"  ✓ {pkg} instalado")
            else:
                log(f"  ⚠ npm install falhou: {inst.stderr[:100]}")
        except subprocess.TimeoutExpired:
            log(f"  ⚠ timeout instalando {pkg}")
        except FileNotFoundError:
            log("  ⚠ npm não encontrado no PATH")
        except Exception as e:
            log(f"  ⚠ erro: {e}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop() -> None:
    load_env()
    log("mcp_warmer.py started (Sprint 36 — cold-start reduction)")
    log(f"Intervalo: {INTERVAL_MINUTES} min | Timeout por MCP: {WARMUP_TIMEOUT_S}s")

    # Garante npm packages na primeira execução
    ensure_npm_packages()

    while True:
        log("--- Início do ciclo mcp-warmer ---")
        try:
            warm_cycle()
        except Exception as e:
            log(f"[main] Erro no ciclo: {e}")
        log("--- Ciclo concluído ---")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_loop()
