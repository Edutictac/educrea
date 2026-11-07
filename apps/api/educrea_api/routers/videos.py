from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProjectVideo, User
from ..security import current_user, require_csrf
from ..services import videos as service
from .projects import project_for_owner

router = APIRouter(prefix="/projects/{project_id}/videos", tags=["videos"])


class VideoOut(BaseModel):
    id: UUID
    path: str
    media_type: str
    size: int
    description: str
    credit: str
    duration_seconds: int
    resolution: str
    model_config = ConfigDict(from_attributes=True)


class VideoUpdate(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    credit: str = Field(default="", max_length=300)


def video_for_owner(db: Session, project_id: UUID, video_id: UUID, user_id: UUID) -> ProjectVideo:
    project_for_owner(db, project_id, user_id)
    return service.video_for_project(db, project_id, video_id)


@router.get("", response_model=list[VideoOut])
def list_videos(project_id: UUID, user: User = Depends(current_user),
                db: Session = Depends(get_db)) -> list[ProjectVideo]:
    project_for_owner(db, project_id, user.id)
    return service.videos_for(db, project_id)


@router.post("", response_model=VideoOut, status_code=201)
async def upload_video(project_id: UUID, request: Request, filename: str = Query(min_length=1, max_length=200),
                       description: str = Query(min_length=1, max_length=300), credit: str = Query(default="", max_length=300),
                       duration: int = Query(default=0, ge=0, le=15), resolution: str = Query(default="", max_length=10),
                       user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> ProjectVideo:
    project_for_owner(db, project_id, user.id)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > service.MAX_VIDEO_BYTES:
        raise HTTPException(413, "El vídeo supera los 30 MB")
    data = await request.body()
    return service.add(db, project_id, filename, data, description, credit, duration, resolution)


@router.get("/{video_id}/content")
def video_content(project_id: UUID, video_id: UUID, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> Response:
    video = video_for_owner(db, project_id, video_id, user.id)
    return Response(video.data, media_type=video.media_type, headers={
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300",
        "Content-Disposition": "inline"})


@router.patch("/{video_id}", response_model=VideoOut)
def update_video(project_id: UUID, video_id: UUID, data: VideoUpdate,
                 user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> ProjectVideo:
    video = video_for_owner(db, project_id, video_id, user.id)
    if not data.description.strip():
        raise HTTPException(422, "Describe el vídeo para que sea accesible")
    video.description, video.credit = data.description.strip(), data.credit.strip()
    db.commit()
    db.refresh(video)
    return video


@router.delete("/{video_id}", status_code=204)
def delete_video(project_id: UUID, video_id: UUID, user: User = Depends(require_csrf),
                 db: Session = Depends(get_db)) -> None:
    db.delete(video_for_owner(db, project_id, video_id, user.id))
    db.commit()
