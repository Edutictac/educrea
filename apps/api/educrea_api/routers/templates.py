import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProjectFile, User
from ..models.entities import utcnow
from ..security import current_user, require_csrf
from ..services import templates as service
from .files import validate_content
from .projects import project_for_owner

router = APIRouter(tags=["templates"])

BRIEF_FIELDS = ("title", "instructions", "language", "level", "accessibility", "area", "course", "illustrations")


class ApplyTemplate(BaseModel):
    template: str = Field(min_length=1, max_length=40)
    brief: dict = Field(default_factory=dict)


@router.get("/templates")
def list_templates(_user: User = Depends(current_user)) -> list[dict]:
    return service.catalog()


@router.post("/projects/{project_id}/template", status_code=201)
def apply_template(project_id: UUID, data: ApplyTemplate, user: User = Depends(require_csrf),
                   db: Session = Depends(get_db)) -> dict:
    """Starts an EMPTY project from a template: writes the brief (activity.json) and the template files."""
    project = project_for_owner(db, project_id, user.id)
    template = service.get(data.template)
    if db.scalar(select(func.count(ProjectFile.id)).where(ProjectFile.project_id == project_id)):
        raise HTTPException(409, "Las plantillas solo se aplican a proyectos vacíos")
    brief = {key: data.brief[key] for key in BRIEF_FIELDS if key in data.brief}
    if "illustrations" in brief:
        brief["illustrations"] = brief["illustrations"] is True  # only a flag: never text for the prompt
    brief["title"] = str(brief.get("title") or project.title)[:160]
    brief["language"] = "va" if brief.get("language") == "va" else "es"
    brief.update(kind="ficha" if template.kind == "ficha" else "actividad", template=template.id)
    files = {"activity.json": json.dumps(brief, ensure_ascii=False, indent=2) + "\n",
             **service.initial_files(template.id, brief)}
    for content in files.values():
        validate_content(content)
    db.add_all(ProjectFile(project_id=project_id, path=path, content=content) for path, content in files.items())
    project.updated_at = utcnow()
    db.commit()
    return {"template": template.id, "files": sorted(files)}


ENGINE_UPDATABLE = ("style.css", "comun.js", "script.js")  # index.html keeps the teacher's title and language


def current_engine(template_id: str) -> dict[str, str]:
    return {path: content for path, content in service.initial_files(template_id, {}).items() if path in ENGINE_UPDATABLE}


def project_template(db: Session, project_id: UUID) -> tuple[str | None, dict[str, ProjectFile]]:
    rows = {row.path: row for row in db.scalars(select(ProjectFile).where(ProjectFile.project_id == project_id))}
    brief_file = rows.get("activity.json")
    try:
        brief = json.loads(brief_file.content) if brief_file else {}
    except ValueError:
        brief = {}
    template = brief.get("template") if isinstance(brief, dict) else None
    if template not in service.TEMPLATES or service.TEMPLATES[template].kind != "interactiva":
        return None, rows
    return template, rows


@router.get("/projects/{project_id}/template")
def template_status(project_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Says whether the engine files of an interactive template project are older than the current engine."""
    project_for_owner(db, project_id, user.id)
    template, rows = project_template(db, project_id)
    if template is None:
        return {"template": None, "outdated": []}
    outdated = [path for path, content in current_engine(template).items() if path in rows and rows[path].content != content]
    return {"template": template, "outdated": outdated}


@router.post("/projects/{project_id}/template/update")
def update_engine(project_id: UUID, user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> dict:
    """Replaces the engine files with the current version. datos.js and index.html are never touched; the previous
    versions stay in the file history, so the update can be undone from there."""
    project = project_for_owner(db, project_id, user.id)
    template, rows = project_template(db, project_id)
    if template is None:
        raise HTTPException(409, "Este proyecto no usa una plantilla interactiva")
    updated = []
    for path, content in current_engine(template).items():
        row = rows.get(path)
        if row is not None and row.content != content:
            row.content = content
            row.version += 1
            updated.append(path)
    if updated:
        project.updated_at = utcnow()
        db.commit()
    return {"template": template, "updated": updated}
