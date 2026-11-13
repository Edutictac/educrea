from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ProjectAsset, User
from ..security import current_user, require_csrf
from ..services import assets as service
from ..services import image_banks
from .projects import project_for_owner

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"])


class AssetOut(BaseModel):
    id: UUID
    path: str
    media_type: str
    size: int
    alt: str
    credit: str
    model_config = ConfigDict(from_attributes=True)


class AssetUpdate(BaseModel):
    alt: str = Field(min_length=1, max_length=300)
    credit: str = Field(default="", max_length=300)


class BankImport(BaseModel):
    provider: Literal["arasaac"]
    id: int = Field(ge=1, le=10_000_000)
    alt: str = Field(min_length=1, max_length=300)
    credit: str = Field(default="", max_length=300)


def asset_for_owner(db: Session, project_id: UUID, asset_id: UUID, user_id: UUID) -> ProjectAsset:
    project_for_owner(db, project_id, user_id)
    asset = db.scalar(select(ProjectAsset).where(ProjectAsset.id == asset_id, ProjectAsset.project_id == project_id))
    if asset is None:
        raise HTTPException(404, "Imagen no encontrada")
    return asset


@router.get("", response_model=list[AssetOut])
def list_assets(project_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[ProjectAsset]:
    project_for_owner(db, project_id, user.id)
    return service.assets_for(db, project_id)


@router.post("", response_model=AssetOut, status_code=201)
async def upload_asset(project_id: UUID, request: Request, filename: str = Query(min_length=1, max_length=200),
                       alt: str = Query(default="", max_length=300), credit: str = Query(default="", max_length=300),
                       user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> ProjectAsset:
    """The image travels as the raw request body, like sources. Only PNG and JPEG, checked by content."""
    project_for_owner(db, project_id, user.id)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > service.MAX_IMAGE_BYTES:
        raise HTTPException(413, "La imagen supera los 2 MB")
    data = await request.body()
    return service.add(db, project_id, filename, data, alt, credit)


@router.post("/from-bank", response_model=AssetOut, status_code=201)
def import_from_bank(project_id: UUID, data: BankImport, user: User = Depends(require_csrf),
                     db: Session = Depends(get_db)) -> ProjectAsset:
    """Downloads a free image server-side and stores it in the project library with its attribution."""
    project_for_owner(db, project_id, user.id)
    image = image_banks.pictogram(data.id, 500)
    credit = data.credit.strip() or image_banks.credit_for(data.id)
    return service.add(db, project_id, f"arasaac-{data.id}.png", image, data.alt, credit)


@router.get("/{asset_id}/content")
def asset_content(project_id: UUID, asset_id: UUID, user: User = Depends(current_user),
                  db: Session = Depends(get_db)) -> Response:
    asset = asset_for_owner(db, project_id, asset_id, user.id)
    return Response(asset.data, media_type=asset.media_type, headers={
        "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cache-Control": "private, max-age=300", "Content-Disposition": "inline"})


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(project_id: UUID, asset_id: UUID, data: AssetUpdate, user: User = Depends(require_csrf),
                 db: Session = Depends(get_db)) -> ProjectAsset:
    asset = asset_for_owner(db, project_id, asset_id, user.id)
    if not data.alt.strip():
        raise HTTPException(422, "Describe la imagen (texto alternativo) para que sea accesible")
    asset.alt, asset.credit = data.alt.strip(), data.credit.strip()
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/{asset_id}", status_code=204)
def delete_asset(project_id: UUID, asset_id: UUID, user: User = Depends(require_csrf),
                 db: Session = Depends(get_db)) -> None:
    db.delete(asset_for_owner(db, project_id, asset_id, user.id))
    db.commit()
