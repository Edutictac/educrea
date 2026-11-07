"""Local listening resources. No network fetches, server decoding or AI transcription."""
import hashlib
import re
import unicodedata
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Project, ProjectAudio

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_PROJECT_BYTES = 50 * 1024 * 1024
MAX_AUDIOS = 10
EXTENSIONS = {"audio/wav": ".wav", "audio/mpeg": ".mp3", "audio/ogg": ".ogg"}


def sniff(data: bytes) -> str:
    if len(data) >= 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE" and b"fmt " in data[:128]:
        return "audio/wav"
    if data.startswith(b"OggS") and (b"OpusHead" in data[:256] or b"\x01vorbis" in data[:256]):
        return "audio/ogg"
    offset = 0
    if data.startswith(b"ID3") and len(data) >= 10 and all(byte < 128 for byte in data[6:10]):
        offset = 10 + sum(byte << shift for byte, shift in zip(data[6:10], (21, 14, 7, 0)))
        if data[5] & 16:
            offset += 10
    frame = data[offset:offset + 4]
    if (len(frame) == 4 and frame[0] == 255 and frame[1] & 224 == 224
            and (frame[1] >> 3) & 3 != 1 and (frame[1] >> 1) & 3 != 0
            and (frame[2] >> 4) not in (0, 15) and (frame[2] >> 2) & 3 != 3):
        return "audio/mpeg"
    raise HTTPException(422, "Solo se admiten audios MP3, WAV u Ogg (Vorbis/Opus), comprobados por contenido")


def audios_for(db: Session, project_id: UUID) -> list[ProjectAudio]:
    return list(db.scalars(select(ProjectAudio).where(ProjectAudio.project_id == project_id).order_by(ProjectAudio.path)))


def add(db: Session, project_id: UUID, filename: str, data: bytes, description: str,
        transcript: str, credit: str) -> ProjectAudio:
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "El audio supera los 10 MB")
    if not description.strip() or not transcript.strip():
        raise HTTPException(422, "Añade un título y una transcripción o descripción de lo que se escucha")
    media_type = sniff(data)
    # Serialize library limits on PostgreSQL; the caller has already checked ownership.
    db.execute(select(Project.id).where(Project.id == project_id).with_for_update()).one()
    count, total = db.execute(select(func.count(ProjectAudio.id), func.coalesce(func.sum(ProjectAudio.size), 0))
                              .where(ProjectAudio.project_id == project_id)).one()
    if count >= MAX_AUDIOS or total + len(data) > MAX_PROJECT_BYTES:
        raise HTTPException(409, "Límite de audios alcanzado: 10 archivos y 50 MB por proyecto")
    digest = hashlib.sha256(data).hexdigest()
    if db.scalar(select(ProjectAudio.id).where(ProjectAudio.project_id == project_id, ProjectAudio.sha256 == digest)):
        raise HTTPException(409, "Este audio ya está en el proyecto")
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
    folded = unicodedata.normalize("NFKD", stem.lower())
    name = re.sub(r"[^a-z0-9]+", "-", "".join(c for c in folded if not unicodedata.combining(c))).strip("-")[:80] or "audio"
    extension = EXTENSIONS[media_type]
    path = f"audios/{name}{extension}"
    taken = {audio.path for audio in audios_for(db, project_id)}
    number = 2
    while path in taken:
        path = f"audios/{name}-{number}{extension}"
        number += 1
    audio = ProjectAudio(project_id=project_id, path=path, media_type=media_type, size=len(data), sha256=digest,
                         description=description.strip(), transcript=transcript.strip(), credit=credit.strip(), data=data)
    db.add(audio)
    db.commit()
    db.refresh(audio)
    return audio


def for_prompt(audios: list[ProjectAudio]) -> list[dict]:
    return [{"path": audio.path, "description": audio.description, "transcript": audio.transcript,
             "credit": audio.credit} for audio in audios]


def credits_text(audios: list[ProjectAudio]) -> str:
    return "Audios del proyecto\n\n" + "\n".join(
        f"- {audio.path}: {audio.description} — {audio.credit or 'sin crédito indicado'}" for audio in audios) + "\n"
