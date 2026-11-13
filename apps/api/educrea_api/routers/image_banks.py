from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ..models import User
from ..security import current_user
from ..services import image_banks

router = APIRouter(prefix="/image-banks", tags=["image-banks"])

HEADERS = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox",
           "Cache-Control": "private, max-age=86400", "Content-Disposition": "inline"}


@router.get("")
def providers(user: User = Depends(current_user)) -> dict:
    return {"providers": [{
        "id": image_banks.PROVIDER,
        "name": "ARASAAC",
        "description": "Pictogramas del portal aragonés de comunicación aumentativa y alternativa",
        "license": image_banks.LICENSE,
        "license_url": image_banks.LICENSE_URL,
        "commercial_use": image_banks.COMMERCIAL_USE,
        "requires_key": False,
    }]}


@router.get("/arasaac/search")
def search(q: str = Query(min_length=1, max_length=80), language: str = Query(default="es", max_length=2),
           user: User = Depends(current_user)) -> dict:
    return image_banks.search(q, language)


@router.get("/arasaac/{pictogram_id}/thumbnail")
def thumbnail(pictogram_id: int, user: User = Depends(current_user)) -> Response:
    return Response(image_banks.pictogram(pictogram_id, 300), media_type="image/png", headers=HEADERS)


@router.get("/arasaac/{pictogram_id}/content")
def content(pictogram_id: int, user: User = Depends(current_user)) -> Response:
    return Response(image_banks.pictogram(pictogram_id, 500), media_type="image/png", headers=HEADERS)
