import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProjectFile, User
from ..security import current_user
from ..services import assets, converter, materials, render
from .files import file_for_owner
from .projects import project_for_owner

router = APIRouter(prefix="/projects/{project_id}", tags=["materials"])


def markdown_for_owner(db: Session, project_id: UUID, file_id: UUID, user: User) -> ProjectFile:
    file = file_for_owner(db, project_id, file_id, user.id)
    if not file.path.lower().endswith(".md"):
        raise HTTPException(422, "Solo se pueden mostrar archivos Markdown")
    return file


def download_name(value: str, extension: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", value).strip("-.")[:80] + extension


def attachment(content: bytes | str, media_type: str, filename: str) -> Response:
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.get("/files/{file_id}/render")
def render_file(project_id: UUID, file_id: UUID, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> dict:
    file = markdown_for_owner(db, project_id, file_id, user)
    return {"html": materials.render_markdown(file.content, assets.assets_for(db, project_id)), "title": materials.title_of(file.path, file.content),
            "version": file.version}


@router.get("/files/{file_id}/export.html")
def export_file_html(project_id: UUID, file_id: UUID, user: User = Depends(current_user),
                     db: Session = Depends(get_db)) -> Response:
    file = markdown_for_owner(db, project_id, file_id, user)
    return attachment(materials.export_html(file.path, file.content, assets=assets.assets_for(db, project_id)), "text/html; charset=utf-8",
                      download_name(file.path.rsplit(".", 1)[0], ".html"))


@router.get("/files/{file_id}/export.png")
def export_infographic_png(project_id: UUID, file_id: UUID, width: int = Query(1200, ge=100, le=2000),
                           height: int = Query(900, ge=100, le=4000), user: User = Depends(current_user),
                           db: Session = Depends(get_db)) -> Response:
    file = file_for_owner(db, project_id, file_id, user.id)
    if not file.path.lower().endswith(".html"):
        raise HTTPException(422, "Solo se pueden exportar a PNG archivos HTML")
    files = {row.path: row.content for row in db.scalars(select(ProjectFile).where(ProjectFile.project_id == project_id))}
    data = render.render_png(file.content, files, width, height, assets.assets_for(db, project_id))
    return attachment(data, "image/png", download_name(file.path.rsplit(".", 1)[0], ".png"))


@router.get("/files/{file_id}/export.{fmt}")
def export_file_converted(project_id: UUID, file_id: UUID, fmt: str, user: User = Depends(current_user),
                          db: Session = Depends(get_db)) -> Response:
    if fmt not in converter.FORMATS:
        raise HTTPException(404, "Formato no encontrado")
    file = markdown_for_owner(db, project_id, file_id, user)
    data = converter.convert(file.content, materials.title_of(file.path, file.content), fmt,
                             assets.assets_for(db, project_id))
    return attachment(data, converter.FORMATS[fmt][1], download_name(file.path.rsplit(".", 1)[0], f".{fmt}"))


@router.get("/export.zip")
def export_project_zip(project_id: UUID, user: User = Depends(current_user),
                       db: Session = Depends(get_db)) -> Response:
    project = project_for_owner(db, project_id, user.id)
    rows = db.scalars(select(ProjectFile).where(ProjectFile.project_id == project_id).order_by(ProjectFile.path))
    return attachment(materials.export_zip([(row.path, row.content) for row in rows], assets.assets_for(db, project_id)), "application/zip",
                      download_name(project.slug, ".zip"))
