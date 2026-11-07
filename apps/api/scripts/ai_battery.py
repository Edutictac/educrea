"""Battery of typical teacher requests against the real free AI models.

Measures, per model, how many requests come out valid at the first attempt (applied automatically), how many stay
pending because validation found problems, and how many fail. It goes through the real API in-process, on a COPY of
the database, with the BYOK keys of an existing account (never printed). Only invented classroom content is sent.

Run with scripts/ai_battery.sh (it loads the dev environment). Options:
  --email teacher@example.org   account whose keys are used (or EDUCREA_BATTERY_EMAIL)
  --models gemini:gemini-3.5-flash-lite,groq:openai/gpt-oss-120b   (default: every confirmed free model)
  --tasks cuestionario,ficha    (default: all)
  --pause 4                     seconds between requests (free tiers limit requests per minute)
  --auto                        «IA automática», as teachers use it: no model chosen, the API falls back by itself
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DB = ROOT / "data" / "educrea.db"
OUT_DIR = ROOT / "data" / "battery"


def copy_database() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "battery.db"
    target.unlink(missing_ok=True)
    with sqlite3.connect(f"file:{SOURCE_DB}?mode=ro", uri=True) as source, sqlite3.connect(target) as copy:
        source.backup(copy)  # consistent copy even while the dev API is running
    return target


# Point the app at the copy BEFORE importing it (the engine is created at import time).
DB_COPY = copy_database()
os.environ["EDUCREA_DATABASE_URL"] = f"sqlite:///{DB_COPY}"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from educrea_api.db import engine  # noqa: E402
from educrea_api.main import app  # noqa: E402
from educrea_api.models import AiCredential, User  # noqa: E402
from educrea_api.security import COOKIE_NAME, new_session  # noqa: E402

RETIRED = {"nvidia", "mistral"}  # see docs/ai-engine.md: no longer offered as free providers

ACCESS = {"large_text": False, "high_contrast": False}
TASKS: list[dict] = [
    {"id": "cuestionario", "template": "cuestionario", "brief": {"title": "El ciclo del agua", "language": "es",
     "level": "primaria", "area": "Ciencias de la Naturaleza", "course": "4.º de Primaria",
     "instructions": "Cuestionario de 6 preguntas sobre evaporación, condensación, precipitación y escorrentía."}},
    {"id": "emparejar", "template": "emparejar", "brief": {"title": "Animals i hàbitats", "language": "va",
     "level": "primaria", "area": "Coneixement del medi", "course": "2n de Primària",
     "instructions": "Aparellar sis animals amb el seu hàbitat: bosc, mar, desert, riu, muntanya i pol."}},
    {"id": "ordenar", "template": "ordenar", "brief": {"title": "Cómo plantar una semilla", "language": "es",
     "level": "primaria", "area": "Ciencias de la Naturaleza", "course": "1.º de Primaria",
     "instructions": "Ordenar los pasos para plantar una semilla de judía en un vaso y cuidarla."}},
    {"id": "tarjetas", "template": "tarjetas", "brief": {"title": "Instruments de l'orquestra", "language": "va",
     "level": "primaria", "area": "Música", "course": "5é de Primària",
     "instructions": "Targetes de repàs: instrument per una cara, família i com sona per l'altra. Huit targetes."}},
    {"id": "clasificar", "template": "clasificar", "brief": {"title": "Vertebrados e invertebrados", "language": "es",
     "level": "primaria", "area": "Ciencias de la Naturaleza", "course": "3.º de Primaria",
     "instructions": "Clasificar diez animales en vertebrados o invertebrados."}},
    {"id": "lectura", "template": "lectura", "brief": {"title": "L'hort de l'escola", "language": "va",
     "level": "primaria", "area": "Valencià: llengua i literatura", "course": "3r de Primària",
     "instructions": "Conte breu en tres parts sobre un grup que cuida l'hort de l'escola, amb una pregunta "
                     "de comprensió després de cada part."}},
    {"id": "ficha", "template": "ficha", "brief": {"title": "Fracciones equivalentes", "language": "es",
     "level": "primaria", "area": "Matemáticas", "course": "5.º de Primaria",
     "instructions": "Ficha para practicar fracciones equivalentes con dibujos y ejemplos de la vida diaria."}},
    {"id": "situacion", "situacion": True, "brief": {"title": "L'hort escolar", "language": "va", "level": "primaria",
     "area": "Coneixement del medi", "course": "4t de Primària",
     "instructions": "Situació d'aprenentatge sobre l'hort escolar: cicle de les plantes, alimentació saludable "
                     "i treball cooperatiu. Producte final: guia de l'hort per a altres cursos."}},
    {"id": "dua", "dua_of": "ficha", "path": "ficha.md",
     "needs": "Grupo con dos alumnos con dislexia y uno con TDAH; algunos alumnos acaban de llegar y aún no dominan el castellano."},
]


class Battery:
    def __init__(self, client: TestClient, csrf: str):
        self.client, self.csrf = client, csrf

    def post(self, url: str, body: dict):
        return self.client.post(url, json=body, headers={"X-CSRF-Token": self.csrf})

    def project(self, title: str) -> str:
        response = self.post("/api/projects", {"title": f"[batería] {title}", "description": "Batería de pruebas con IA"})
        response.raise_for_status()
        return response.json()["id"]

    def prepare(self, task: dict) -> str:
        project_id = self.project(task["brief"]["title"])
        brief = {**task["brief"], "accessibility": ACCESS}
        if task.get("situacion"):
            content = json.dumps({"kind": "situacion", **brief, "sessions": 4}, ensure_ascii=False, indent=2) + "\n"
            self.post(f"/api/projects/{project_id}/files", {"path": "activity.json", "content": content}).raise_for_status()
        else:
            self.post(f"/api/projects/{project_id}/template", {"template": task["template"], "brief": brief}).raise_for_status()
        return project_id

    def run(self, task: dict, provider: str, model: str, projects: dict[str, str]) -> dict:
        choice = {} if provider == "auto" else {"provider": provider, "model": model}
        started = time.monotonic()
        if "dua_of" in task:
            project_id = projects.get(task["dua_of"])
            if project_id is None:
                return {"outcome": "skipped", "detail": f"la tarea {task['dua_of']} no generó nada"}
            response = self.post(f"/api/projects/{project_id}/ai/dua",
                                 {**choice, "path": task["path"], "needs": task["needs"], "auto_apply": True})
        else:
            project_id = self.prepare(task)
            response = self.post(f"/api/projects/{project_id}/ai/from-brief", choice)
        seconds = round(time.monotonic() - started, 1)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = response.text[:300]
            return {"outcome": "error", "http": response.status_code, "detail": str(detail)[:400], "seconds": seconds}
        proposal = response.json()
        projects[task["id"]] = project_id
        grounding = proposal.get("grounding") or {}
        return {"outcome": "applied" if proposal["status"] == "applied" else "review",
                "model_used": f"{proposal['provider']}:{proposal['model']}", "seconds": seconds,
                "usage": proposal.get("usage"), "files": [change["path"] for change in proposal["changes"]],
                "problems": (grounding.get("template_problems") or grounding.get("sections_missing")
                             or (None if grounding.get("supported", True) else "sin respaldo en las fuentes")),
                "grounding": grounding or None}


def confirmed_models(db: Session, user: User) -> list[tuple[str, str]]:
    credentials = db.scalars(select(AiCredential).where(AiCredential.user_id == user.id)).all()
    return [(c.provider, model) for c in credentials if c.provider not in RETIRED
            for model in sorted(c.free_confirmations or {})]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", default=os.environ.get("EDUCREA_BATTERY_EMAIL", ""), required=not os.environ.get("EDUCREA_BATTERY_EMAIL"))
    parser.add_argument("--models", default="")
    parser.add_argument("--tasks", default="")
    parser.add_argument("--pause", type=float, default=4)
    parser.add_argument("--auto", action="store_true")
    args = parser.parse_args()

    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == args.email))
        if user is None:
            print(f"No existe la cuenta {args.email} en la base de desarrollo", file=sys.stderr)
            return 2
        models = ([("auto", "auto")] if args.auto else
                  [tuple(item.split(":", 1)) for item in args.models.split(",") if item] or confirmed_models(db, user))
        token, csrf = new_session(db, user)
    wanted = {item for item in args.tasks.split(",") if item}
    tasks = [task for task in TASKS if not wanted or task["id"] in wanted]
    if not models:
        print("La cuenta no tiene modelos gratuitos confirmados", file=sys.stderr)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    results: list[dict] = []
    with TestClient(app) as client:
        client.cookies.set(COOKIE_NAME, token)
        battery = Battery(client, csrf)
        for provider, model in models:
            projects: dict[str, str] = {}
            for task in tasks:
                try:
                    result = battery.run(task, provider, model, projects)
                except Exception as exc:  # report and keep going: one broken task must not hide the rest
                    result = {"outcome": "crash", "detail": f"{type(exc).__name__}: {exc}"[:400]}
                results.append({"task": task["id"], "provider": provider, "model": model, **result})
                line = f"{provider}:{model:<40} {task['id']:<13} {result['outcome']:<8} {result.get('seconds', '')}s"
                if result["outcome"] != "applied":
                    line += f"  {result.get('http', '')} {result.get('problems') or result.get('detail') or ''}"[:200]
                print(line, flush=True)
                time.sleep(args.pause)

    (OUT_DIR / f"battery-{stamp}.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    print(f"\nResumen ({len(tasks)} encargos por modelo):")
    for provider, model in models:
        rows = [r for r in results if r["provider"] == provider and r["model"] == model]
        counts = {k: sum(r["outcome"] == k for r in rows) for k in ("applied", "review", "error", "crash", "skipped")}
        print(f"  {provider}:{model:<42} válidas {counts['applied']}/{len(rows)}  revisión {counts['review']}  "
              f"error {counts['error'] + counts['crash']}  omitidas {counts['skipped']}")
    print(f"\nInforme: {OUT_DIR / f'battery-{stamp}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
