import base64
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import current_user, require_csrf
from ..services.ai import images as image_service
from ..services.ai import included, quotas
from ..services.ai.providers.base import ProviderError
from ..services.ai.providers.gemini_image import GeminiImageProvider, get_gemini_image_provider
from .projects import project_for_owner

router = APIRouter(tags=["images"])


class ImageEstimateInput(BaseModel):
    prompt: str = Field(min_length=3, max_length=image_service.MAX_PROMPT_CHARS)
    model: str = Field(min_length=1, max_length=100)
    aspect_ratio: Literal["1:1", "4:3", "3:4", "16:9", "9:16"] = image_service.DEFAULT_ASPECT


class ImageGenerateInput(ImageEstimateInput):
    paid_authorized: bool = False
    approved_max_cost_microusd: int | None = Field(default=None, ge=0)
    approved_estimate_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    rights_acknowledged: bool = False
    no_personal_data: bool = False


@router.get("/ai/images/models")
def image_models(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    included_images = image_service.included_status(db, user.id)
    return {"configured": image_service.configured(db, user.id),
            "own_key": image_service.own_key(db, user.id),
            "included": included_images,
            "default": included_images["model"] if included_images else image_service.default_model(),
            "models": image_service.models(),
            "budget": quotas.budget_summary(db, user.id)}


@router.post("/projects/{project_id}/ai/images/estimate")
def estimate_image(project_id: UUID, data: ImageEstimateInput, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> dict:
    project_for_owner(db, project_id, user.id)
    return image_service.estimate(data.prompt, data.model, data.aspect_ratio)


@router.post("/projects/{project_id}/ai/images")
async def generate_image(project_id: UUID, data: ImageGenerateInput, user: User = Depends(require_csrf),
                         db: Session = Depends(get_db),
                         provider: GeminiImageProvider = Depends(get_gemini_image_provider)) -> dict:
    project_for_owner(db, project_id, user.id)
    if not data.rights_acknowledged or not data.no_personal_data:
        raise HTTPException(422, "Confirma que tienes derecho a generar la imagen y que no incluye datos personales")
    estimate = image_service.estimate(data.prompt, data.model, data.aspect_ratio)
    if image_service.uses_included(db, user.id, data.model):
        return await _generate_included(db, user.id, data, estimate, provider)
    if (not data.paid_authorized or data.approved_max_cost_microusd != estimate["maximum_cost_microusd"]
            or data.approved_estimate_fingerprint != estimate["fingerprint"]):
        raise HTTPException(403, "Confirma la estimación actual antes de generar la imagen")
    key = image_service.api_key(db, user.id)
    image_service.check_daily_limit(db, user.id)
    reservation = quotas.reserve_fixed(db, user.id, image_service.PROVIDER, data.model,
                                       estimate["maximum_cost_microusd"])
    maximum = estimate["maximum_cost_microusd"]
    try:
        generated = await provider.generate(key, data.model, data.prompt, data.aspect_ratio, image_service.SIZE)
    except ProviderError as exc:
        # A clear rejection (quota, key, bad request) costs nothing; a timeout or an unreadable answer may have been
        # billed by Google, so it keeps counting against the monthly budget.
        quotas.reconcile_fixed(db, reservation, maximum if exc.consumed_unknown else 0, failed=True)
        raise HTTPException(exc.status_code, str(exc)) from None
    except BaseException:
        quotas.reconcile_fixed(db, reservation, 0, failed=True)
        raise
    try:
        normalized, media_type = image_service.normalize(generated.data)
    except BaseException:
        quotas.reconcile_fixed(db, reservation, maximum, failed=True)  # Google already delivered and billed it
        raise
    quotas.reconcile_fixed(db, reservation, maximum)
    return _result(data, estimate, normalized, media_type)


async def _generate_included(db: Session, user_id, data: ImageGenerateInput, estimate: dict,
                             provider: GeminiImageProvider) -> dict:
    """IA EduCrea: institutional key and weekly image quota; no cost confirmation, since the teacher pays nothing."""
    maximum = estimate["maximum_cost_microusd"]
    reservation = included.reserve_image(db, user_id, data.model, maximum)
    try:
        generated = await provider.generate(included.image_key(), data.model, data.prompt, data.aspect_ratio,
                                            image_service.SIZE)
    except ProviderError as exc:
        included.reconcile_image(db, reservation, maximum if exc.consumed_unknown else 0, useful=False)
        included.logger.warning("included_ai_image_provider_error status=%s", exc.status_code)
        if exc.status_code == 429:
            raise HTTPException(429, "IA EduCrea no puede generar imágenes ahora. Inténtalo más tarde.") from None
        raise HTTPException(exc.status_code, str(exc)) from None
    except BaseException:
        included.reconcile_image(db, reservation, maximum, useful=False)  # unknown: may have been billed
        raise
    try:
        normalized, media_type = image_service.normalize(generated.data)
    except BaseException:
        included.reconcile_image(db, reservation, maximum, useful=False)
        raise
    included.reconcile_image(db, reservation, maximum, useful=True)
    return {**_result(data, estimate, normalized, media_type), "cost_microusd": 0, "included": True}


def _result(data: ImageGenerateInput, estimate: dict, normalized: bytes, media_type: str) -> dict:
    return {"provider": image_service.PROVIDER, "model": data.model, "size": image_service.SIZE,
            "aspect_ratio": data.aspect_ratio, "media_type": media_type,
            "image_base64": base64.b64encode(normalized).decode(),
            "size_bytes": len(normalized), "cost_microusd": estimate["maximum_cost_microusd"],
            "fingerprint": estimate["fingerprint"],
            "suggested_credit": image_service.suggested_credit(data.model),
            "suggested_filename": image_service.suggested_filename()}
