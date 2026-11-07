import base64
import binascii
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProjectAudio, User
from ..security import current_user, require_csrf
from ..services import audios as service
from .projects import project_for_owner

router = APIRouter(prefix="/projects/{project_id}/audios", tags=["audios"])


class AudioOut(BaseModel):
    id: UUID
    path: str
    media_type: str
    size: int
    description: str
    transcript: str
    credit: str
    model_config = ConfigDict(from_attributes=True)


class AudioMetadata(BaseModel):
    description: str = Field(min_length=1, max_length=300, pattern=r"\S")
    transcript: str = Field(min_length=1, max_length=12000, pattern=r"\S")
    credit: str = Field(default="", max_length=300)


def audio_for_owner(db: Session, project_id: UUID, audio_id: UUID, user_id: UUID) -> ProjectAudio:
    project_for_owner(db, project_id, user_id)
    audio = db.scalar(select(ProjectAudio).where(ProjectAudio.id == audio_id, ProjectAudio.project_id == project_id))
    if audio is None:
        raise HTTPException(404, "Audio no encontrado")
    return audio


@router.get("", response_model=list[AudioOut])
def list_audios(project_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project_for_owner(db, project_id, user.id)
    return service.audios_for(db, project_id)


class AudioUpload(AudioMetadata):
    filename: str = Field(min_length=1, max_length=200)
    audio_base64: str = Field(min_length=1, max_length=4 * ((service.MAX_AUDIO_BYTES + 2) // 3))


@router.post("", response_model=AudioOut, status_code=201)
async def upload_audio(project_id: UUID, request: Request,
                       user: User = Depends(require_csrf), db: Session = Depends(get_db)):
    project_for_owner(db, project_id, user.id)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 4 * ((service.MAX_AUDIO_BYTES + 2) // 3) + 100000:
            raise HTTPException(413, "El audio supera los 10 MB")
        body.extend(chunk)
    try:
        metadata = AudioUpload.model_validate_json(bytes(body))
        data = base64.b64decode(metadata.audio_base64, validate=True)
    except (ValidationError, ValueError, binascii.Error):
        raise HTTPException(422, "Revisa el archivo, título y transcripción (máximo 12000 caracteres)") from None
    return service.add(db, project_id, metadata.filename, data, metadata.description, metadata.transcript, metadata.credit)


@router.get("/{audio_id}/content")
def audio_content(project_id: UUID, audio_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    audio = audio_for_owner(db, project_id, audio_id, user.id)
    return Response(audio.data, media_type=audio.media_type, headers={
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=300",
        "Content-Security-Policy": "default-src 'none'; sandbox", "Content-Disposition": "inline"})


@router.patch("/{audio_id}", response_model=AudioOut)
def update_audio(project_id: UUID, audio_id: UUID, data: AudioMetadata,
                 user: User = Depends(require_csrf), db: Session = Depends(get_db)):
    audio = audio_for_owner(db, project_id, audio_id, user.id)
    audio.description, audio.transcript, audio.credit = data.description.strip(), data.transcript.strip(), data.credit.strip()
    db.commit()
    db.refresh(audio)
    return audio


@router.delete("/{audio_id}", status_code=204)
def delete_audio(project_id: UUID, audio_id: UUID, user: User = Depends(require_csrf), db: Session = Depends(get_db)):
    db.delete(audio_for_owner(db, project_id, audio_id, user.id))
    db.commit()
