"""Image library of a project: PNG and JPEG uploaded by the teacher.

Images are referenced from activities and documents with a relative path (imagenes/<name>.png). They are never
fetched from the network: preview, reading view and every export embed them as data: URIs or copy them next to the
document. SVG is not accepted because it can carry scripts. Only PNG and JPEG are allowed so that the same image
works in HTML, PNG, DOCX and PDF (xelatex reads both).
"""

import base64
import hashlib
import re
import unicodedata
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ProjectAsset

PREFIX = "imagenes/"
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_PROJECT_BYTES = 20 * 1024 * 1024
MAX_ASSETS = 50
SIGNATURES = {"image/png": (b"\x89PNG\r\n\x1a\n",), "image/jpeg": (b"\xff\xd8\xff",)}
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg"}
REFERENCE = re.compile(r"""(?P<lead>(?:src\s*=\s*["']|url\(\s*["']?|\]\())\s*(?:\./)?(?P<path>imagenes/[A-Za-z0-9._-]+)""")


def sniff(data: bytes) -> str:
    for media_type, signatures in SIGNATURES.items():
        if any(data.startswith(signature) for signature in signatures):
            return media_type
    raise HTTPException(422, "Solo se admiten imágenes PNG o JPEG")


def safe_name(filename: str, media_type: str) -> str:
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
    folded = unicodedata.normalize("NFKD", stem.lower())
    clean = re.sub(r"[^a-z0-9]+", "-", "".join(c for c in folded if not unicodedata.combining(c))).strip("-")
    return PREFIX + (clean[:60] or "imagen") + EXTENSIONS[media_type]


def assets_for(db: Session, project_id: UUID) -> list[ProjectAsset]:
    return list(db.scalars(select(ProjectAsset).where(ProjectAsset.project_id == project_id).order_by(ProjectAsset.path)))


def add(db: Session, project_id: UUID, filename: str, data: bytes, alt: str, credit: str) -> ProjectAsset:
    if not data:
        raise HTTPException(422, "El archivo está vacío")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "La imagen supera los 2 MB")
    if not alt.strip():
        raise HTTPException(422, "Describe la imagen (texto alternativo) para que sea accesible")
    media_type = sniff(data)
    count, total = db.execute(select(func.count(ProjectAsset.id), func.coalesce(func.sum(ProjectAsset.size), 0))
                              .where(ProjectAsset.project_id == project_id)).one()
    if count >= MAX_ASSETS:
        raise HTTPException(409, f"Límite de {MAX_ASSETS} imágenes por proyecto alcanzado")
    if total + len(data) > MAX_PROJECT_BYTES:
        raise HTTPException(409, "Las imágenes del proyecto superarían los 20 MB")
    digest = hashlib.sha256(data).hexdigest()
    taken = {path for path in db.scalars(select(ProjectAsset.path).where(ProjectAsset.project_id == project_id))}
    duplicate = db.scalar(select(ProjectAsset).where(ProjectAsset.project_id == project_id, ProjectAsset.sha256 == digest))
    if duplicate is not None:
        raise HTTPException(409, f"Esta imagen ya está en el proyecto como {duplicate.path}")
    path = safe_name(filename, media_type)
    stem, extension = path.rsplit(".", 1)
    number = 2
    while path in taken:
        path = f"{stem}-{number}.{extension}"
        number += 1
    asset = ProjectAsset(project_id=project_id, path=path, media_type=media_type, size=len(data), sha256=digest,
                         alt=alt.strip()[:300], credit=credit.strip()[:300], data=data)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def data_uri(asset: ProjectAsset) -> str:
    return f"data:{asset.media_type};base64,{base64.b64encode(asset.data).decode()}"


def embed(text: str, assets: list[ProjectAsset]) -> str:
    """Replaces references to project images (src="imagenes/…", url(imagenes/…), ](imagenes/…)) by data: URIs."""
    by_path = {asset.path: asset for asset in assets}
    if not by_path:
        return text

    def replace(match: re.Match) -> str:
        asset = by_path.get(match.group("path"))
        return match.group("lead") + data_uri(asset) if asset else match.group(0)
    return REFERENCE.sub(replace, text)


def for_prompt(assets: list[ProjectAsset]) -> list[dict]:
    return [{"path": asset.path, "alt": asset.alt, "credit": asset.credit} for asset in assets]


def credits_text(assets: list[ProjectAsset]) -> str:
    lines = ["Imágenes del proyecto", ""]
    lines += [f"- {asset.path}: {asset.alt}" + (f" — {asset.credit}" if asset.credit else " — sin crédito indicado")
              for asset in assets]
    return "\n".join(lines) + "\n"
