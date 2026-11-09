"""BYOK video generation with Gemini Omni Flash: short clips, per-second prices and preview before saving."""
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import AiUsage, IncludedAiLimits, BetaAdminAudit
from .. import videos as video_service
from .credentials import decrypt_key, personal_credential
from .pricing import Price, cost
from .temporary_credentials import credential as temporary_credential

MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
PROVIDER = "gemini"
RESOLUTIONS = ("360p", "720p")
DURATIONS = (4, 5, 6)
ASPECT_RATIOS = ("16:9", "9:16")
DEFAULT_DURATION = 6
DEFAULT_ASPECT = "16:9"
MAX_PROMPT_CHARS = 1000


def catalog() -> dict[str, dict[str, dict]]:
    try:
        raw = json.loads(get_settings().video_models_json)
        if not isinstance(raw, dict):
            raise ValueError("catalog")
        parsed: dict[str, dict[str, dict]] = {}
        for provider, models in raw.items():
            if provider != PROVIDER or not isinstance(models, dict):
                raise ValueError("provider")
            parsed[provider] = {}
            for model, resolutions in models.items():
                if not MODEL_ID.fullmatch(model) or not isinstance(resolutions, dict):
                    raise ValueError("model")
                input_rate = resolutions.get("input_microusd_per_million", 0)
                if type(input_rate) is not int or not 0 <= input_rate <= 100000000:
                    raise ValueError("input")
                entries = {}
                for resolution, value in resolutions.items():
                    if resolution == "input_microusd_per_million":
                        continue
                    if resolution not in RESOLUTIONS or not isinstance(value, dict):
                        raise ValueError("resolution")
                    second = value.get("second_microusd")
                    if type(second) is not int or not 0 < second <= 1000000:
                        raise ValueError("price")
                    entries[resolution] = {"second_microusd": second}
                if not entries:
                    raise ValueError("empty")
                parsed[provider][model] = {"resolutions": entries, "input_microusd_per_million": input_rate}
        return parsed
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(503, "Catálogo de vídeo de IA no válido") from exc


def models() -> list[dict]:
    result = []
    for model, entry in catalog().get(PROVIDER, {}).items():
        result.append({"provider": PROVIDER, "model": model,
                       "resolutions": entry["resolutions"],
                       "durations": list(DURATIONS),
                       "input_microusd_per_million": entry["input_microusd_per_million"]})
    return sorted(result, key=lambda item: min(value["second_microusd"] for value in item["resolutions"].values()))


def default_model() -> str | None:
    available = models()
    return available[0]["model"] if available else None


def default_resolution(model: str) -> str:
    entry = catalog().get(PROVIDER, {}).get(model) or {}
    resolutions = entry.get("resolutions") or {}
    return min(resolutions, key=lambda name: resolutions[name]["second_microusd"]) if resolutions else "360p"


def price_for(model: str, resolution: str) -> dict:
    entry = catalog().get(PROVIDER, {}).get(model) or {}
    value = (entry.get("resolutions") or {}).get(resolution)
    if value is None:
        raise HTTPException(403, "Modelo o resolución de vídeo no habilitados")
    return {"second_microusd": value["second_microusd"],
            "input_microusd_per_million": entry.get("input_microusd_per_million", 0)}


def estimate(prompt: str, model: str, resolution: str, duration: int,
             aspect_ratio: str = DEFAULT_ASPECT) -> dict:
    if resolution not in RESOLUTIONS or duration not in DURATIONS or aspect_ratio not in ASPECT_RATIOS:
        raise HTTPException(422, "Parámetros de vídeo no válidos")
    price = price_for(model, resolution)
    max_input_tokens = len(prompt.encode("utf-8")) + 1024
    input_microusd = cost(max_input_tokens, 0, Price(price["input_microusd_per_million"], 0))
    maximum = price["second_microusd"] * duration + input_microusd
    fingerprint = hashlib.sha256(json.dumps({
        "provider": PROVIDER, "model": model, "resolution": resolution, "duration": duration,
        "aspect_ratio": aspect_ratio, "prompt": prompt,
        "second_microusd": price["second_microusd"],
        "input_microusd_per_million": price["input_microusd_per_million"],
    }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"provider": PROVIDER, "model": model, "resolution": resolution, "duration": duration,
            "aspect_ratio": aspect_ratio, "max_input_tokens": max_input_tokens,
            "maximum_cost_microusd": maximum, "second_microusd": price["second_microusd"],
            "input_microusd": input_microusd, "fingerprint": fingerprint}


def configured(db: Session, user_id: UUID) -> bool:
    if temporary_credential(db, user_id, PROVIDER):
        return True
    return personal_credential(db, user_id, PROVIDER) is not None


def api_key(db: Session, user_id: UUID) -> str:
    temporary = temporary_credential(db, user_id, PROVIDER)
    if temporary:
        return temporary["key"].get_secret_value()
    credential = personal_credential(db, user_id, PROVIDER)
    if credential is None:
        raise HTTPException(409, "Configura tu clave de Gemini antes de generar vídeos")
    return decrypt_key(credential.ciphertext)


def daily_count(db: Session, user_id: UUID | None = None) -> int:
    today = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    video_models = list(catalog().get(PROVIDER, {}))
    if not video_models:
        return 0
    query = select(func.count(AiUsage.id)).where(
        AiUsage.provider == PROVIDER, AiUsage.model.in_(video_models), AiUsage.created_at >= today)
    if user_id is not None:
        query = query.where(AiUsage.user_id == user_id)
    return int(db.scalar(query) or 0)


def limits_info(db: Session) -> dict:
    settings = get_settings()
    row = db.get(IncludedAiLimits, 1, populate_existing=True)
    daily = row.videos_daily_limit if row else None
    global_daily = row.videos_global_daily_limit if row else None
    return {"daily_limit": daily if daily is not None else settings.ai_daily_video_requests,
            "global_daily_limit": (global_daily if global_daily is not None
                                   else settings.ai_daily_global_video_requests),
            "daily_custom": daily, "global_daily_custom": global_daily, "enabled": bool(models())}


def set_limits(db: Session, daily: int, global_daily: int, actor_id: UUID) -> dict:
    from .included import lock, now_utc
    from ..beta_admin import require_role
    lock(db)
    try:
        require_role(db, actor_id)
        row = db.get(IncludedAiLimits, 1, populate_existing=True)
        if row is None:
            row = IncludedAiLimits(id=1, updated_at=now_utc())
            db.add(row)
        row.videos_daily_limit = daily
        row.videos_global_daily_limit = global_daily
        row.updated_at = now_utc()
        db.add(BetaAdminAudit(actor_id=actor_id, action="video_limits_updated"))
        db.commit()
        return limits_info(db)
    except BaseException:
        db.rollback()
        raise


def quota_status(db: Session, user_id: UUID) -> dict:
    limits = limits_info(db)
    used = daily_count(db, user_id)
    global_remaining = (max(0, limits["global_daily_limit"] - daily_count(db))
                        if limits["global_daily_limit"] else None)
    tomorrow = datetime.combine(datetime.now(timezone.utc).date() + timedelta(days=1),
                                time.min, tzinfo=timezone.utc)
    remaining = max(0, limits["daily_limit"] - used)
    return {"daily_limit": limits["daily_limit"], "used": used, "remaining": remaining,
            "available_remaining": min(remaining, global_remaining) if global_remaining is not None else remaining,
            "renews_at": tomorrow.isoformat(), "enabled": limits["enabled"]}


def check_daily_limit(db: Session, user_id: UUID) -> None:
    limits = limits_info(db)
    if daily_count(db, user_id) >= limits["daily_limit"]:
        raise HTTPException(429, "Has alcanzado el límite diario de vídeos generados")
    if limits["global_daily_limit"] and daily_count(db) >= limits["global_daily_limit"]:
        raise HTTPException(429, "La instalación ha alcanzado hoy su límite de vídeos generados")


def reserve(db: Session, user_id: UUID, model: str, maximum_cost: int) -> UUID:
    from . import quotas
    from .included import lock
    # Same transaction lock as paid reservations: two users cannot bypass the shared daily cap.
    lock(db)
    check_daily_limit(db, user_id)
    return quotas.reserve_fixed(db, user_id, PROVIDER, model, maximum_cost)


def validate_generated(data: bytes) -> str:
    if len(data) > video_service.MAX_VIDEO_BYTES:
        raise HTTPException(413, "El vídeo generado supera los 30 MB")
    return video_service.sniff(data)


def suggested_credit(model: str) -> str:
    return f"Generado con IA (Google Gemini, {model}, {datetime.now(timezone.utc).date().isoformat()})"


def suggested_filename() -> str:
    return "video-ia.mp4"
