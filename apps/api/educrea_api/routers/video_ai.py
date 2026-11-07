import base64
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import current_user, require_csrf
from ..services.ai import quotas
from ..services.ai import videos as video_service
from ..services.ai.providers.base import ProviderError
from ..services.ai.providers.gemini_video import GeminiVideoProvider, get_gemini_video_provider
from .projects import project_for_owner

router = APIRouter(tags=["video-ai"])


class VideoEstimateInput(BaseModel):
    prompt: str = Field(min_length=3, max_length=video_service.MAX_PROMPT_CHARS)
    model: str = Field(min_length=1, max_length=100)
    resolution: Literal["360p", "720p"] = "360p"
    duration: int = Field(default=video_service.DEFAULT_DURATION, ge=4, le=6)
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"


class VideoGenerateInput(VideoEstimateInput):
    paid_authorized: bool = False
    approved_max_cost_microusd: int | None = Field(default=None, ge=0)
    approved_estimate_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    rights_acknowledged: bool = False
    no_personal_data: bool = False


@router.get("/ai/videos/models")
def video_models(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    default = video_service.default_model()
    return {"configured": video_service.configured(db, user.id),
            "default": default,
            "default_resolution": video_service.default_resolution(default) if default else None,
            "models": video_service.models(),
            "budget": quotas.budget_summary(db, user.id)}


@router.post("/projects/{project_id}/ai/videos/estimate")
def estimate_video(project_id: UUID, data: VideoEstimateInput, user: User = Depends(current_user),
                   db: Session = Depends(get_db)) -> dict:
    project_for_owner(db, project_id, user.id)
    return video_service.estimate(data.prompt, data.model, data.resolution, data.duration, data.aspect_ratio)


@router.post("/projects/{project_id}/ai/videos")
async def generate_video(project_id: UUID, data: VideoGenerateInput, user: User = Depends(require_csrf),
                         db: Session = Depends(get_db),
                         provider: GeminiVideoProvider = Depends(get_gemini_video_provider)) -> dict:
    project_for_owner(db, project_id, user.id)
    if not data.rights_acknowledged or not data.no_personal_data:
        raise HTTPException(422, "Confirma que tienes derecho a generar el vídeo y que no incluye datos personales")
    estimate = video_service.estimate(data.prompt, data.model, data.resolution, data.duration, data.aspect_ratio)
    if (not data.paid_authorized or data.approved_max_cost_microusd != estimate["maximum_cost_microusd"]
            or data.approved_estimate_fingerprint != estimate["fingerprint"]):
        raise HTTPException(403, "Confirma la estimación actual antes de generar el vídeo")
    key = video_service.api_key(db, user.id)
    video_service.check_daily_limit(db, user.id)
    reservation = quotas.reserve_fixed(db, user.id, video_service.PROVIDER, data.model,
                                       estimate["maximum_cost_microusd"])
    maximum = estimate["maximum_cost_microusd"]
    try:
        generated = await provider.generate(key, data.model, data.prompt, data.aspect_ratio,
                                            data.resolution, data.duration)
    except ProviderError as exc:
        # A clear rejection (quota, key, bad request) costs nothing; a timeout or an unreadable answer may have been
        # billed by Google, so it keeps counting against the monthly budget.
        quotas.reconcile_fixed(db, reservation, maximum if exc.consumed_unknown else 0, failed=True)
        raise HTTPException(exc.status_code, str(exc)) from None
    except BaseException:
        quotas.reconcile_fixed(db, reservation, 0, failed=True)
        raise
    try:
        media_type = video_service.validate_generated(generated.data)
    except BaseException:
        quotas.reconcile_fixed(db, reservation, maximum, failed=True)  # Google already delivered and billed it
        raise
    quotas.reconcile_fixed(db, reservation, maximum)
    return {"provider": video_service.PROVIDER, "model": data.model, "resolution": data.resolution,
            "duration": data.duration, "aspect_ratio": data.aspect_ratio, "media_type": media_type,
            "video_base64": base64.b64encode(generated.data).decode(),
            "size_bytes": len(generated.data), "cost_microusd": estimate["maximum_cost_microusd"],
            "fingerprint": estimate["fingerprint"],
            "suggested_credit": video_service.suggested_credit(data.model),
            "suggested_filename": video_service.suggested_filename()}
