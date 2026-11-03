import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Project, User
from ..schemas import ProjectCreate, ProjectOut, ProjectUpdate
from ..security import current_user, require_csrf

router = APIRouter(prefix="/projects", tags=["projects"])


def project_for_owner(db: Session, project_id: UUID, owner_id: UUID) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == owner_id))
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado")
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc())))


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, user: User = Depends(require_csrf),
                   db: Session = Depends(get_db)) -> Project:
    title = data.title.strip()
    if not title:
        raise HTTPException(422, "El título no puede estar vacío")
    slug_base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "proyecto"
    slug = slug_base
    suffix = 2
    while db.scalar(select(Project.id).where(Project.owner_id == user.id, Project.slug == slug)):
        slug = f"{slug_base[:55]}-{suffix}"
        suffix += 1
    project = Project(owner_id=user.id, slug=slug, title=title, description=data.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: UUID, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> Project:
    return project_for_owner(db, project_id, user.id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: UUID, data: ProjectUpdate, user: User = Depends(require_csrf),
                   db: Session = Depends(get_db)) -> Project:
    project = project_for_owner(db, project_id, user.id)
    if data.title is not None:
        if not data.title.strip():
            raise HTTPException(422, "El título no puede estar vacío")
        project.title = data.title.strip()
    if data.description is not None:
        project.description = data.description
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: UUID, user: User = Depends(require_csrf),
                   db: Session = Depends(get_db)) -> None:
    db.delete(project_for_owner(db, project_id, user.id))
    db.commit()

