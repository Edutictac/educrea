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

BRIEF_FIELDS = ("title", "instructions", "language", "level", "accessibility", "area", "course")


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
