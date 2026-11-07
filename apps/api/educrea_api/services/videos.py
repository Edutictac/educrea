"""Small project video library. Videos are kept out of the image asset table and its 2 MB limit."""
import hashlib
import re
import unicodedata
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ProjectVideo

PREFIX = "videos/"
MAX_VIDEO_BYTES = 30 * 1024 * 1024
MAX_PROJECT_VIDEO_BYTES = 200 * 1024 * 1024
MAX_VIDEOS = 10
MEDIA_TYPE = "video/mp4"


def sniff(data: bytes) -> str:
    # ISO base media files put the ``ftyp`` box at offset 4.
    if len(data) < 12 or data[4:8] != b"ftyp":
        raise HTTPException(422, "Solo se admiten vídeos MP4")
    return MEDIA_TYPE


def safe_name(filename: str) -> str:
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
    folded = unicodedata.normalize("NFKD", stem.lower())
    clean = re.sub(r"[^a-z0-9]+", "-", "".join(c for c in folded if not unicodedata.combining(c))).strip("-")
    return PREFIX + (clean[:80] or "video") + ".mp4"


def videos_for(db: Session, project_id: UUID) -> list[ProjectVideo]:
    return list(db.scalars(select(ProjectVideo).where(ProjectVideo.project_id == project_id)
                           .order_by(ProjectVideo.path)))


def video_for_project(db: Session, project_id: UUID, video_id: UUID) -> ProjectVideo:
    video = db.scalar(select(ProjectVideo).where(ProjectVideo.id == video_id,
                                                ProjectVideo.project_id == project_id))
    if video is None:
        raise HTTPException(404, "Vídeo no encontrado")
    return video


def add(db: Session, project_id: UUID, filename: str, data: bytes, description: str, credit: str,
        duration_seconds: int = 0, resolution: str = "") -> ProjectVideo:
    if not data:
        raise HTTPException(422, "El vídeo está vacío")
    if len(data) > MAX_VIDEO_BYTES:
        raise HTTPException(413, "El vídeo supera los 30 MB")
    if not description.strip():
        raise HTTPException(422, "Describe el vídeo para que sea accesible")
    media_type = sniff(data)
    count, total = db.execute(select(func.count(ProjectVideo.id), func.coalesce(func.sum(ProjectVideo.size), 0))
                              .where(ProjectVideo.project_id == project_id)).one()
    if count >= MAX_VIDEOS:
        raise HTTPException(409, f"Límite de {MAX_VIDEOS} vídeos por proyecto alcanzado")
    if total + len(data) > MAX_PROJECT_VIDEO_BYTES:
        raise HTTPException(409, "Los vídeos del proyecto superarían los 200 MB")
    digest = hashlib.sha256(data).hexdigest()
    duplicate = db.scalar(select(ProjectVideo).where(ProjectVideo.project_id == project_id,
                                                    ProjectVideo.sha256 == digest))
    if duplicate is not None:
        raise HTTPException(409, f"Este vídeo ya está en el proyecto como {duplicate.path}")
    taken = {path for path in db.scalars(select(ProjectVideo.path).where(ProjectVideo.project_id == project_id))}
    path = safe_name(filename)
    stem, extension = path.rsplit(".", 1)
    number = 2
    while path in taken:
        path = f"{stem}-{number}.{extension}"
        number += 1
    video = ProjectVideo(project_id=project_id, path=path, media_type=media_type, size=len(data),
                         sha256=digest, description=description.strip()[:300], credit=credit.strip()[:300],
                         duration_seconds=max(0, min(15, duration_seconds)), resolution=resolution[:10],
                         data=data)
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def credits_text(videos: list[ProjectVideo]) -> str:
    lines = ["Vídeos del proyecto", ""]
    lines += [f"- {video.path}: {video.description}" + (f" — {video.credit}" if video.credit else " — sin crédito indicado")
              for video in videos]
    return "\n".join(lines) + "\n"
