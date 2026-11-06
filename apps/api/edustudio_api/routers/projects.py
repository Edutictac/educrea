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


def unique_slug(db: Session, owner_id: UUID, title: str) -> str:
    slug_base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "proyecto"
    slug = slug_base
    suffix = 2
    while db.scalar(select(Project.id).where(Project.owner_id == owner_id, Project.slug == slug)):
        slug = f"{slug_base[:55]}-{suffix}"
        suffix += 1
    return slug


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, user: User = Depends(require_csrf),
                   db: Session = Depends(get_db)) -> Project:
    title = data.title.strip()
    if not title:
        raise HTTPException(422, "El título no puede estar vacío")
    project = Project(owner_id=user.id, slug=unique_slug(db, user.id, title), title=title, description=data.description)
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



@router.post("/{project_id}/duplicate", response_model=ProjectOut, status_code=201)
def duplicate_project(project_id: UUID, user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> Project:
    """Copy of a project to reuse it with another group: files, images and starting material (sources with their
    fragments). History, AI proposals and usage are not copied; the copy starts at version 1."""
    from ..models import ProjectAsset, ProjectFile, Source, SourceChunk

    original = project_for_owner(db, project_id, user.id)
    title = f"{original.title} (copia)"[:160]
    copy = Project(owner_id=user.id, slug=unique_slug(db, user.id, title), title=title, description=original.description)
    db.add(copy)
    db.flush()
    db.info["version_source"] = "duplicate"
    for row in db.scalars(select(ProjectFile).where(ProjectFile.project_id == project_id)):
        db.add(ProjectFile(project_id=copy.id, path=row.path, content=row.content))
    for asset in db.scalars(select(ProjectAsset).where(ProjectAsset.project_id == project_id)):
        db.add(ProjectAsset(project_id=copy.id, path=asset.path, media_type=asset.media_type, size=asset.size,
                            sha256=asset.sha256, alt=asset.alt, credit=asset.credit, data=asset.data))
    for source in db.scalars(select(Source).where(Source.project_id == project_id)):
        clone = Source(project_id=copy.id, title=source.title, filename=source.filename, kind=source.kind,
                       pages=source.pages, chars=source.chars, chunk_count=source.chunk_count, url=source.url,
                       fetched_at=source.fetched_at)
        db.add(clone)
        db.flush()
        db.add_all(SourceChunk(source_id=clone.id, project_id=copy.id, ordinal=chunk.ordinal, heading=chunk.heading,
                               page=chunk.page, text=chunk.text)
                   for chunk in db.scalars(select(SourceChunk).where(SourceChunk.source_id == source.id)))
    db.commit()
    db.info.pop("version_source", None)
    db.refresh(copy)
    return copy
