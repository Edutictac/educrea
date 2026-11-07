from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import FileVersion, Project, ProjectFile, User
from ..models.entities import utcnow
from ..security import current_user, require_csrf
from ..services import history
from .files import MAX_FILES, validate_path
from .projects import project_for_owner

router = APIRouter(prefix="/projects/{project_id}/history", tags=["history"])


class VersionSummary(BaseModel):
    id: UUID
    path: str
    version: int
    source: str
    created_at: datetime
    size: int
    model_config = ConfigDict(from_attributes=True)


class VersionOut(VersionSummary):
    content: str


def summary(row: FileVersion) -> VersionSummary:
    return VersionSummary(id=row.id, path=row.path, version=row.version, source=row.source,
                          created_at=row.created_at, size=len(row.content.encode("utf-8")))


def version_for_owner(db: Session, project_id: UUID, version_id: UUID, user_id: UUID) -> FileVersion:
    row = db.scalar(select(FileVersion).join(Project, Project.id == FileVersion.project_id).where(
        FileVersion.id == version_id, FileVersion.project_id == project_id, Project.owner_id == user_id))
    if row is None:
        raise HTTPException(404, "Versión no encontrada")
    return row


@router.get("/paths")
def history_paths(project_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    project_for_owner(db, project_id, user.id)
    existing = set(db.scalars(select(ProjectFile.path).where(ProjectFile.project_id == project_id)))
    rows = db.execute(select(FileVersion.path, func.count(FileVersion.id)).where(
        FileVersion.project_id == project_id).group_by(FileVersion.path).order_by(FileVersion.path)).all()
    return [{"path": path, "versions": count, "deleted": path not in existing} for path, count in rows]


@router.get("", response_model=list[VersionSummary])
def list_versions(project_id: UUID, path: str = Query(max_length=200), user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> list[VersionSummary]:
    project_for_owner(db, project_id, user.id)
    rows = db.scalars(select(FileVersion).where(FileVersion.project_id == project_id, FileVersion.path == path)
                      .order_by(FileVersion.version.desc()))
    return [summary(row) for row in rows]


@router.get("/{version_id}", response_model=VersionOut)
def get_version(project_id: UUID, version_id: UUID, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> VersionOut:
    row = version_for_owner(db, project_id, version_id, user.id)
    return VersionOut(**summary(row).model_dump(), content=row.content)


@router.post("/{version_id}/restore", response_model=VersionSummary)
def restore_version(project_id: UUID, version_id: UUID, user: User = Depends(require_csrf),
                    db: Session = Depends(get_db)) -> VersionSummary:
    """Restoring never rewrites history: it saves the old content as a new version."""
    project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id).with_for_update())
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado")
    old = version_for_owner(db, project_id, version_id, user.id)
    validate_path(old.path)
    file = db.scalar(select(ProjectFile).where(ProjectFile.project_id == project_id, ProjectFile.path == old.path))
    db.info["version_source"] = "restore"
    if file is None:
        if db.scalar(select(func.count(ProjectFile.id)).where(ProjectFile.project_id == project_id)) >= MAX_FILES:
            raise HTTPException(409, "Límite de archivos alcanzado")
        file = ProjectFile(project_id=project_id, path=old.path, content=old.content,
                           version=history.next_version(db, project_id, old.path))
        db.add(file)
    elif file.content != old.content:
        file.content = old.content
        file.version += 1
    project.updated_at = utcnow()
    db.commit()
    db.info.pop("version_source", None)
    row = db.scalar(select(FileVersion).where(FileVersion.project_id == project_id, FileVersion.path == old.path,
                                              FileVersion.version == file.version))
    return summary(row)
