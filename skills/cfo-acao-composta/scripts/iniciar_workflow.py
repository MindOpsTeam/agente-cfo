#!/usr/bin/env python3
"""
iniciar_workflow.py — Gerencia workflows multi-step com checkpoint.

Uso:
  python3 iniciar_workflow.py --nome "cobrar-inadimplentes" --steps "listar,confirmar,executar"
  python3 iniciar_workflow.py --listar
  python3 iniciar_workflow.py --retomar <id>
  python3 iniciar_workflow.py --step-ok <id> --step-nome "listar" --dados '{"count": 10}'
  python3 iniciar_workflow.py --step-fail <id> --step-nome "executar" --erro "HTTP 401"
  python3 iniciar_workflow.py --finalizar <id>
  python3 iniciar_workflow.py --format json --listar
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

WORKFLOWS_DIR = Path.home() / ".agente-cfo" / "memory" / "workflows"
TIMEOUT_MINUTES = 10

FORMAT = "text"
CMD = None
WF_ID = None
NOME = None
STEPS = None
STEP_NOME = None
DADOS = None
ERRO = None
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--format" and i + 1 < len(sys.argv): FORMAT = sys.argv[i+1]; i += 2
    elif a == "--listar": CMD = "listar"; i += 1
    elif a == "--nome" and i + 1 < len(sys.argv): NOME = sys.argv[i+1]; i += 2
    elif a == "--steps" and i + 1 < len(sys.argv): STEPS = sys.argv[i+1].split(","); i += 2
    elif a == "--retomar" and i + 1 < len(sys.argv): CMD = "retomar"; WF_ID = sys.argv[i+1]; i += 2
    elif a == "--step-ok" and i + 1 < len(sys.argv): CMD = "step-ok"; WF_ID = sys.argv[i+1]; i += 2
    elif a == "--step-fail" and i + 1 < len(sys.argv): CMD = "step-fail"; WF_ID = sys.argv[i+1]; i += 2
    elif a == "--finalizar" and i + 1 < len(sys.argv): CMD = "finalizar"; WF_ID = sys.argv[i+1]; i += 2
    elif a == "--step-nome" and i + 1 < len(sys.argv): STEP_NOME = sys.argv[i+1]; i += 2
    elif a == "--dados" and i + 1 < len(sys.argv):
        try: DADOS = json.loads(sys.argv[i+1])
        except: DADOS = {"raw": sys.argv[i+1]}
        i += 2
    elif a == "--erro" and i + 1 < len(sys.argv): ERRO = sys.argv[i+1]; i += 2
    else: i += 1


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_wf(wf_id: str) -> dict | None:
    f = WORKFLOWS_DIR / f"{wf_id}.json"
    if f.exists():
        try: return json.loads(f.read_text())
        except: pass
    return None


def save_wf(wf: dict):
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    (WORKFLOWS_DIR / f"{wf['id']}.json").write_text(
        json.dumps(wf, indent=2, ensure_ascii=False))


def is_expired(wf: dict) -> bool:
    updated = wf.get("updated_at", "")
    if not updated: return False
    try:
        dt = datetime.fromisoformat(updated)
        elapsed = (datetime.now(timezone.utc) - dt).total_seconds() / 60
        return elapsed > TIMEOUT_MINUTES
    except: return False


def list_workflows() -> list:
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    wfs = []
    for f in sorted(WORKFLOWS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            wf = json.loads(f.read_text())
            if wf.get("status") not in ("finalizado", "expirado"):
                wfs.append(wf)
        except: pass
    return wfs


def main():
    if CMD == "listar" or (NOME is None and CMD is None):
        wfs = list_workflows()
        if FORMAT == "json":
            print(json.dumps(wfs, ensure_ascii=False)); return
        if not wfs:
            print("  ✅ Nenhum workflow ativo."); return
        print(f"⚙️  Workflows ativos ({len(wfs)}):")
        for wf in wfs:
            step = wf.get("step_atual", "?")
            status = "⏳" if wf["status"] == "em_andamento" else "✅"
            expired = " (EXPIRADO)" if is_expired(wf) else ""
            print(f"  {status} [{wf['id'][:8]}] {wf['nome']:<30} step: {step}{expired}")
        return

    if NOME and CMD is None:
        # Criar novo workflow
        wf_id = str(uuid.uuid4())[:8]
        steps = STEPS or ["preparar", "confirmar", "executar", "registrar", "confirmar-dono"]
        wf = {
            "id": wf_id,
            "nome": NOME,
            "status": "em_andamento",
            "steps": steps,
            "step_atual": steps[0] if steps else "início",
            "step_index": 0,
            "resultados": {},
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        save_wf(wf)
        result = {"id": wf_id, "nome": NOME, "steps": steps, "step_atual": wf["step_atual"]}
        if FORMAT == "json":
            print(json.dumps(result, ensure_ascii=False)); return
        print(f"⚙️  Workflow criado: [{wf_id}] '{NOME}'")
        print(f"  Steps: {' → '.join(steps)}")
        print(f"  Próximo: {steps[0]}")
        return

    if CMD in ("step-ok", "step-fail") and WF_ID:
        wf = load_wf(WF_ID)
        if not wf:
            print(json.dumps({"error": f"Workflow {WF_ID} não encontrado"}) if FORMAT == "json"
                  else f"❌ Workflow {WF_ID} não encontrado")
            return
        if is_expired(wf):
            wf["status"] = "expirado"; save_wf(wf)
            print(json.dumps({"error": "Workflow expirado"}) if FORMAT == "json"
                  else f"⏰ Workflow {WF_ID} expirado (>{TIMEOUT_MINUTES}min sem atividade)")
            return

        step = STEP_NOME or wf.get("step_atual", "?")
        if CMD == "step-ok":
            wf["resultados"][step] = {"status": "ok", "dados": DADOS, "at": now_iso()}
            steps = wf.get("steps", [])
            idx = wf.get("step_index", 0) + 1
            wf["step_index"] = idx
            wf["step_atual"] = steps[idx] if idx < len(steps) else "concluído"
            if idx >= len(steps):
                wf["status"] = "finalizado"
            wf["updated_at"] = now_iso()
        else:
            wf["resultados"][step] = {"status": "erro", "erro": ERRO, "at": now_iso()}
            wf["ultimo_erro"] = ERRO
            wf["updated_at"] = now_iso()

        save_wf(wf)
        result = {"id": WF_ID, "step": step, "cmd": CMD,
                  "status": wf["status"], "prox_step": wf.get("step_atual")}
        if FORMAT == "json":
            print(json.dumps(result, ensure_ascii=False)); return
        marker = "✅" if CMD == "step-ok" else "❌"
        print(f"⚙️  {marker} Step '{step}' → próximo: {wf.get('step_atual')}")
        return

    if CMD == "retomar" and WF_ID:
        wf = load_wf(WF_ID)
        if not wf:
            print(json.dumps({"error": f"Workflow {WF_ID} não encontrado"}) if FORMAT == "json"
                  else f"❌ Workflow {WF_ID} não encontrado")
            return
        if FORMAT == "json":
            print(json.dumps(wf, ensure_ascii=False)); return
        print(f"⚙️  Retomando [{WF_ID}] '{wf['nome']}'")
        print(f"  Step atual: {wf.get('step_atual')}")
        if wf.get("ultimo_erro"):
            print(f"  Último erro: {wf['ultimo_erro']}")
        return

    if CMD == "finalizar" and WF_ID:
        wf = load_wf(WF_ID)
        if wf:
            wf["status"] = "finalizado"
            wf["updated_at"] = now_iso()
            save_wf(wf)
        print(json.dumps({"id": WF_ID, "finalizado": True}) if FORMAT == "json"
              else f"✅ Workflow {WF_ID} finalizado.")
        return

    print(json.dumps({"error": "Nenhum comando válido fornecido"}) if FORMAT == "json"
          else "Uso: python3 iniciar_workflow.py --nome X [--steps a,b,c] | --listar | --retomar ID")


if __name__ == "__main__":
    main()
