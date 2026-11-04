from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Source, User
from ..security import current_user, require_csrf
from ..services import fetch_url, sources as service
from .projects import project_for_owner

router = APIRouter(prefix="/projects/{project_id}/sources", tags=["sources"])


class SourceOut(BaseModel):
    id: UUID
    title: str
    filename: str
    kind: str
    pages: int
    chars: int
    chunk_count: int
    created_at: datetime
    url: str | None = None
    fetched_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


def source_for_owner(db: Session, project_id: UUID, source_id: UUID, user_id: UUID) -> Source:
    project_for_owner(db, project_id, user_id)
    source = db.scalar(select(Source).where(Source.id == source_id, Source.project_id == project_id))
    if source is None:
        raise HTTPException(404, "Fuente no encontrada")
    return source


@router.get("", response_model=list[SourceOut])
def list_sources(project_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Source]:
    project_for_owner(db, project_id, user.id)
    return list(db.scalars(select(Source).where(Source.project_id == project_id).order_by(Source.created_at)))


@router.post("", response_model=SourceOut, status_code=201)
async def upload_source(project_id: UUID, request: Request, filename: str = Query(min_length=1, max_length=200),
                        title: str = Query(default="", max_length=200), user: User = Depends(require_csrf),
                        db: Session = Depends(get_db)) -> Source:
    """The file travels as the raw request body (no multipart dependency); only its text is kept."""
    project_for_owner(db, project_id, user.id)
    if db.scalar(select(func.count(Source.id)).where(Source.project_id == project_id)) >= service.MAX_SOURCES:
        raise HTTPException(409, f"Límite de {service.MAX_SOURCES} fuentes por proyecto alcanzado")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > service.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "El archivo supera los 25 MB")
    data = await request.body()
    pages = await run_in_threadpool(service.extract, filename, data)
    return service.ingest(db, project_id, title.strip() or filename.rsplit(".", 1)[0], filename, pages)


class UrlInput(BaseModel):
    url: HttpUrl
    title: str = Field(default="", max_length=200)


@router.post("/url", response_model=SourceOut, status_code=201)
def add_url_source(project_id: UUID, data: UrlInput, user: User = Depends(require_csrf),
                   db: Session = Depends(get_db)) -> Source:
    """Download a public document (HTML, text, Markdown or PDF) instead of uploading the file."""
    project_for_owner(db, project_id, user.id)
    if db.scalar(select(func.count(Source.id)).where(Source.project_id == project_id)) >= service.MAX_SOURCES:
        raise HTTPException(409, f"Límite de {service.MAX_SOURCES} fuentes por proyecto alcanzado")
    final_url, extension, content = fetch_url.fetch(str(data.url))
    name = fetch_url.filename(final_url, extension)
    title = data.title.strip() or fetch_url.suggested_title(content, extension, name.rsplit(".", 1)[0])
    pages = service.extract(name, content)
    return service.ingest(db, project_id, title, name, pages, url=final_url)


@router.post("/{source_id}/refresh", response_model=SourceOut)
def refresh_source(project_id: UUID, source_id: UUID, user: User = Depends(require_csrf),
                   db: Session = Depends(get_db)) -> Source:
    source = source_for_owner(db, project_id, source_id, user.id)
    if not source.url:
        raise HTTPException(409, "Esta fuente no viene de una URL")
    return service.reingest(db, source)


@router.delete("/{source_id}", status_code=204)
def delete_source(project_id: UUID, source_id: UUID, user: User = Depends(require_csrf),
                  db: Session = Depends(get_db)) -> None:
    db.delete(source_for_owner(db, project_id, source_id, user.id))
    db.commit()


@router.get("/{source_id}/search")
def search_source(project_id: UUID, source_id: UUID, q: str = Query(min_length=2, max_length=300),
                  user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Shows which passages the assistant would receive for a request: lets the teacher check the source."""
    source_for_owner(db, project_id, source_id, user.id)
    return [{key: value for key, value in item.items() if key != "chunk_id"}
            for item in service.retrieve(db, project_id, [source_id], q, budget=12_000, limit=8)]
