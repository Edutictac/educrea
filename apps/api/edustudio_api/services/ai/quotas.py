"""Internal limits. Only resources nobody else limits are capped here:

- Shared resources (the administrator's Ollama): per-user and per-installation daily limits.
- Personal-key providers (Gemini, OpenRouter, Groq, OpenAI, Anthropic): the provider enforces the real quota on the
  user's own account. We keep one generation at a time and a high daily request cap against runaway loops.
- Paid models: additionally bounded by the user's monthly budget.
Counts are internal estimates, never provider balances.
"""

from datetime import datetime, time, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import AiBudget, AiUsage, User
from .pricing import Price, cost

RESERVED_TOKENS = 16384
SHARED_PROVIDERS = frozenset({"ollama"})


def _tokens(item: AiUsage) -> int:
    return item.actual_tokens if item.actual_tokens is not None else item.reserved_tokens


def reserve(db: Session, user_id: UUID, provider: str, model: str,
            maximum_cost_microusd: int = 0, price: Price | None = None,
            maximum_tokens: int = RESERVED_TOKENS) -> UUID:
    settings = get_settings()
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(1743004)"))
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(401, "Sesión no válida")
    now = datetime.now(timezone.utc)
    today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    usage = list(db.scalars(select(AiUsage).where(AiUsage.created_at >= today)))
    mine = [item for item in usage if item.user_id == user_id]
    if any(item.status == "reserved" for item in mine):
        raise HTTPException(429, "Ya tienes una generación en curso")
    if provider in SHARED_PROVIDERS:
        shared = [item for item in usage if item.provider in SHARED_PROVIDERS]
        shared_mine = [item for item in shared if item.user_id == user_id]
        if (len(shared_mine) >= settings.ai_daily_user_requests
                or len(shared) >= settings.ai_daily_installation_requests
                or sum(map(_tokens, shared_mine)) + maximum_tokens > settings.ai_daily_user_tokens
                or sum(map(_tokens, shared)) + maximum_tokens > settings.ai_daily_installation_tokens):
            raise HTTPException(429, "Límite diario del servidor de modelos compartido alcanzado")
    elif len([item for item in mine if item.provider not in SHARED_PROVIDERS]) >= settings.ai_daily_personal_requests:
        raise HTTPException(429, "Límite de seguridad diario alcanzado")
    if maximum_cost_microusd:
        if price is None:
            raise HTTPException(500, "Precio no disponible")
        budget = db.get(AiBudget, user_id)
        month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        month_usage = list(db.scalars(select(AiUsage).where(AiUsage.user_id == user_id,
                                                            AiUsage.created_at >= month)))
        spent = sum(item.actual_cost_microusd if item.actual_cost_microusd is not None
                    else item.reserved_cost_microusd for item in month_usage)
        if budget is None or budget.monthly_limit_microusd < spent + maximum_cost_microusd:
            raise HTTPException(429, "Presupuesto mensual insuficiente")
    entry = AiUsage(user_id=user_id, provider=provider, model=model,
                    reserved_tokens=maximum_tokens, status="reserved",
                    mode="paid" if maximum_cost_microusd else "free",
                    reserved_cost_microusd=maximum_cost_microusd,
                    input_rate_microusd=price.input_rate if price else 0,
                    output_rate_microusd=price.output_rate if price else 0)
    db.add(entry)
    db.commit()
    return entry.id


def reconcile(db: Session, reservation_id: UUID, usage: dict | None = None, failed: bool = False) -> None:
    entry = db.get(AiUsage, reservation_id)
    if entry is None or entry.status != "reserved":
        return
    reported = usage or {}
    if reported and any(reported.values()):
        entry.actual_tokens = max(0, int(reported.get("input_tokens", 0))) + max(0, int(reported.get("output_tokens", 0)))
    else:
        # Unknown provider usage remains charged at the reservation ceiling.
        entry.actual_tokens = entry.reserved_tokens
    if entry.mode == "paid":
        entry.actual_cost_microusd = (cost(max(0, int(reported.get("input_tokens", 0))),
                                           max(0, int(reported.get("output_tokens", 0))),
                                           Price(entry.input_rate_microusd, entry.output_rate_microusd))
                                       if reported and any(reported.values()) else entry.reserved_cost_microusd)
    entry.status = "failed" if failed else "completed"
    db.commit()


def summary(db: Session, user_id: UUID) -> dict:
    settings = get_settings()
    today = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    usage = list(db.scalars(select(AiUsage).where(AiUsage.created_at >= today)))
    mine = [item for item in usage if item.user_id == user_id]
    personal = [item for item in mine if item.provider not in SHARED_PROVIDERS]
    shared = [item for item in usage if item.provider in SHARED_PROVIDERS]
    shared_mine = [item for item in shared if item.user_id == user_id]
    return {"requests_used": len(mine), "requests_limit": settings.ai_daily_personal_requests,
            "tokens_used_or_reserved": sum(map(_tokens, mine)),
            "personal_requests_used": len(personal),
            "shared": {"requests_used": len(shared_mine), "requests_limit": settings.ai_daily_user_requests,
                       "tokens_used_or_reserved": sum(map(_tokens, shared_mine)),
                       "tokens_limit": settings.ai_daily_user_tokens,
                       "installation_requests_used": len(shared),
                       "installation_requests_limit": settings.ai_daily_installation_requests}}


def budget_summary(db: Session, user_id: UUID) -> dict:
    now = datetime.now(timezone.utc)
    month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    budget = db.get(AiBudget, user_id)
    usage = list(db.scalars(select(AiUsage).where(AiUsage.user_id == user_id, AiUsage.created_at >= month)))
    return {"monthly_limit_microusd": budget.monthly_limit_microusd if budget else 0,
            "spent_or_reserved_microusd": sum(item.actual_cost_microusd if item.actual_cost_microusd is not None
                                               else item.reserved_cost_microusd for item in usage),
            "maximum_allowed_microusd": get_settings().ai_max_user_budget_microusd}


def set_budget(db: Session, user_id: UUID, limit: int) -> dict:
    if limit > get_settings().ai_max_user_budget_microusd:
        raise HTTPException(422, "El presupuesto supera el máximo permitido")
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(1743004)"))
    db.scalar(select(User).where(User.id == user_id).with_for_update())
    budget = db.get(AiBudget, user_id)
    if budget is None:
        budget = AiBudget(user_id=user_id, monthly_limit_microusd=limit)
        db.add(budget)
    else:
        budget.monthly_limit_microusd = limit
    db.commit()
    return budget_summary(db, user_id)
