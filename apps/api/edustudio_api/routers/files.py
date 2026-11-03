import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Project, ProjectFile, User
from ..models.entities import utcnow
from ..schemas import FileCreate, FileOut, FileSummary, FileUpdate
from ..security import current_user, require_csrf
from .projects import project_for_owner

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])
ALLOWED_EXTENSIONS = (".html", ".css", ".js", ".json")
MAX_FILE_BYTES = 256 * 1024
MAX_FILES = 30
SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_path(path: str) -> None:
    parts = path.split("/")
    if (len(path.encode("utf-8")) > 200 or not parts or len(parts) > 8
            or any(part in {".", ".."} or not SEGMENT.fullmatch(part) for part in parts)
            or not path.lower().endswith(ALLOWED_EXTENSIONS)):
        raise HTTPException(422, "Ruta de archivo no permitida")


def validate_content(content: str) -> None:
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise HTTPException(413, "Archivo demasiado grande")


def file_for_owner(db: Session, project_id: UUID, file_id: UUID, owner_id: UUID) -> ProjectFile:
    file = db.scalar(select(ProjectFile).join(Project).where(
        ProjectFile.id == file_id, ProjectFile.project_id == project_id, Project.owner_id == owner_id))
    if file is None:
        raise HTTPException(404, "Archivo no encontrado")
    return file


@router.get("", response_model=list[FileSummary])
def list_files(project_id: UUID, user: User = Depends(current_user),
               db: Session = Depends(get_db)) -> list[ProjectFile]:
    project_for_owner(db, project_id, user.id)
    return list(db.scalars(select(ProjectFile).where(ProjectFile.project_id == project_id).order_by(ProjectFile.path)))


@router.post("", response_model=FileOut, status_code=201)
def create_file(project_id: UUID, data: FileCreate, user: User = Depends(require_csrf),
                db: Session = Depends(get_db)) -> ProjectFile:
    validate_path(data.path)
    validate_content(data.content)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id).with_for_update())
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado")
    if db.scalar(select(func.count(ProjectFile.id)).where(ProjectFile.project_id == project_id)) >= MAX_FILES:
        raise HTTPException(409, "Límite de archivos alcanzado")
    if db.scalar(select(ProjectFile.id).where(ProjectFile.project_id == project_id, ProjectFile.path == data.path)):
        raise HTTPException(409, "El archivo ya existe")
    file = ProjectFile(project_id=project_id, path=data.path, content=data.content)
    db.add(file)
    project.updated_at = utcnow()
    db.commit()
    db.refresh(file)
    return file


@router.get("/{file_id}", response_model=FileOut)
def get_file(project_id: UUID, file_id: UUID, user: User = Depends(current_user),
             db: Session = Depends(get_db)) -> ProjectFile:
    return file_for_owner(db, project_id, file_id, user.id)


@router.put("/{file_id}", response_model=FileOut)
def update_file(project_id: UUID, file_id: UUID, data: FileUpdate,
                user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> ProjectFile:
    validate_content(data.content)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id).with_for_update())
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado")
    file = file_for_owner(db, project_id, file_id, user.id)
    if file.version != data.expected_version:
        raise HTTPException(409, "El archivo ha cambiado. Recarga antes de guardar")
    file.content = data.content
    file.version += 1
    project.updated_at = utcnow()
    db.commit()
    db.refresh(file)
    return file


@router.delete("/{file_id}", status_code=204)
def delete_file(project_id: UUID, file_id: UUID, expected_version: int = Query(ge=1),
                user: User = Depends(require_csrf),
                db: Session = Depends(get_db)) -> None:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.owner_id == user.id).with_for_update())
    if project is None:
        raise HTTPException(404, "Proyecto no encontrado")
    file = file_for_owner(db, project_id, file_id, user.id)
    if file.version != expected_version:
        raise HTTPException(409, "El archivo ha cambiado. Recarga antes de eliminar")
    db.delete(file)
    project.updated_at = utcnow()
    db.commit()

