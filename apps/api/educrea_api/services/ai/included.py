"""IA EduCrea: institutional configuration and atomic accounting in AiUsage.

No personal credential access, provider conversation IDs, prompts or answers in this ledger.
Money is integer micro-USD; all ceilings use integer arithmetic, never binary floats.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import logging
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select, text, func
from sqlalchemy.orm import Session

from ...config import get_settings
from ...models import AiUsage, AiBudgetAlert, User
from .pricing import Price, cost
from . import access
from .providers.base import ProviderError
from .providers.compatible import CompatibleProvider

logger = logging.getLogger(__name__)
PAUSED = "IA EduCrea no está disponible ahora. Puedes utilizar tu propia API."
EXHAUSTED = ("No tienes cuota mensual suficiente para esta generación de IA EduCrea. "
             "La cuota se renueva el 1 del próximo mes. Puedes seguir utilizando tu propia API.")


def now_utc():
    return datetime.now(timezone.utc)


def period(now):
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start.strftime("%Y-%m"), start, end


def micro_usd(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > 1000000:
            raise ValueError()
        return int((amount * 1000000).to_integral_value(rounding=ROUND_CEILING))
    except (ValueError, InvalidOperation):
        raise HTTPException(503, PAUSED) from None


def credits(amount, conversion, minimum=0):
    return max(minimum, (amount * conversion + 999999) // 1000000)


@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    endpoint: str
    price: Price
    key: str = field(repr=False)


def route(provider):
    if provider not in {"qwen", "deepseek"}:
        raise HTTPException(503, PAUSED)
    s = get_settings()
    key = getattr(s, f"{provider}_api_key")
    model = getattr(s, f"{provider}_model")
    base = getattr(s, f"{provider}_base_url").rstrip('/')
    try:
        url = urlsplit(base)
        _ = url.port
    except ValueError:
        raise HTTPException(503, PAUSED) from None
    from .providers.registry import MODEL_ID
    price = Price(micro_usd(getattr(s, f"{provider}_input_cost_per_million")),
                  micro_usd(getattr(s, f"{provider}_output_cost_per_million")))
    if (not s.free_ai_enabled or not getattr(s, f"{provider}_enabled") or not key
            or not key.get_secret_value().strip() or not model
            or not MODEL_ID.fullmatch(model) or url.scheme != "https" or not url.hostname
            or url.username or url.password or url.query or url.fragment
            or not price.input_rate or not price.output_rate):
        raise HTTPException(503, PAUSED)
    return Route(provider, model, base + "/chat/completions", price, key.get_secret_value())


def adapter(plan):
    extra = {"enable_thinking": False} if plan.provider == "qwen" else {"thinking": {"type": "disabled"}}
    return CompatibleProvider(plan.provider, endpoint=plan.endpoint,
                              max_output_tokens=get_settings().free_ai_max_output_tokens, extra_payload=extra)


def lock(db):
    # Release any authentication/context read transaction before acquiring the shared write lock.
    db.rollback()
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(1743004)"))
    elif db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    else:
        raise HTTPException(503, PAUSED)


def ledger_cost(entry):
    return entry.actual_cost_microusd if entry.actual_cost_microusd is not None else entry.reserved_cost_microusd


def ledger_credits(entry):
    return entry.actual_credits if entry.actual_credits is not None else entry.reserved_credits


def expire(db, now):
    cutoff = now - timedelta(seconds=get_settings().free_ai_reservation_ttl_seconds)
    for item in db.scalars(select(AiUsage).where(AiUsage.mode == "included", AiUsage.status == "reserved",
                                               AiUsage.created_at < cutoff)):
        # A dead worker must not permanently block the user. Unknown institutional spend stays reserved.
        item.status = "expired"
        item.actual_credits = 0
        item.actual_cost_microusd = item.reserved_cost_microusd
        item.finished_at = now
    db.flush()


def totals(db, start):
    return list(db.scalars(select(AiUsage).where(AiUsage.mode == "included", AiUsage.created_at >= start)))


def alert(db, now):
    key, start, _ = period(now)
    limit = micro_usd(get_settings().free_ai_global_monthly_budget_usd)
    spent = sum(map(ledger_cost, totals(db, start)))
    for threshold in (50, 75, 90, 100):
        if limit and spent * 100 >= limit * threshold and not db.get(AiBudgetAlert, (key, threshold)):
            db.add(AiBudgetAlert(period_key=key, threshold=threshold))
            logger.warning("included_ai_budget_threshold period=%s threshold=%s", key, threshold)


def reserve(db, user_id, plan, prompt, task_type="unknown", request_id=None):
    s = get_settings()
    # Conservative upper bound: at most one input token per UTF-8 byte, plus framing.
    maximum_input = len(prompt.encode()) + 1024
    if maximum_input > s.free_ai_max_input_tokens:
        raise HTTPException(413, "El contenido supera el límite por petición de IA EduCrea.")
    maximum_cost = cost(maximum_input, s.free_ai_max_output_tokens, plan.price)
    maximum_credits = credits(maximum_cost, s.free_ai_credits_per_usd, s.free_ai_min_credits_per_request)
    now = now_utc()
    key, start, _ = period(now)
    lock(db)
    try:
        # Recheck the switches and configuration under the lock, before spending.
        access.require_access(db, user_id)
        route(plan.provider)
        if db.get(User, user_id) is None:
            raise HTTPException(401, "Sesión no válida")
        expire(db, now)
        mine = list(db.scalars(select(AiUsage).where(AiUsage.mode == "included", AiUsage.user_id == user_id,
                                                    AiUsage.period_key == key)))
        if sum(map(ledger_credits, mine)) + maximum_credits > s.free_ai_monthly_credits:
            raise HTTPException(429, EXHAUSTED)
        active = db.scalar(select(func.count()).select_from(AiUsage).where(
            AiUsage.mode == "included", AiUsage.user_id == user_id, AiUsage.status == "reserved"))
        if active >= s.free_ai_max_concurrent_requests:
            raise HTTPException(429, "Ya tienes una generación de IA EduCrea en curso.")
        request_id = request_id or uuid4()
        # Rate limits use timestamps, including requests across a month boundary. Retries share request_id.
        recent = list(db.scalars(select(AiUsage).where(AiUsage.mode == "included", AiUsage.user_id == user_id,
                                                      AiUsage.created_at >= now - timedelta(days=1))))
        for seconds, maximum in ((60, s.free_ai_minute_request_limit), (3600, s.free_ai_hourly_request_limit),
                                 (86400, s.free_ai_daily_request_limit)):
            cutoff = (now - timedelta(seconds=seconds)).replace(tzinfo=None)
            ids = {i.request_id for i in recent if i.created_at.replace(tzinfo=None) >= cutoff}
            if request_id not in ids and len(ids) >= maximum:
                raise HTTPException(429, "Has alcanzado el límite temporal de IA EduCrea. Inténtalo más tarde.")
        for begin, limit in ((now.replace(hour=0, minute=0, second=0, microsecond=0),
                               micro_usd(s.free_ai_global_daily_budget_usd)),
                              (start, micro_usd(s.free_ai_global_monthly_budget_usd))):
            if not limit or sum(map(ledger_cost, totals(db, begin))) + maximum_cost > limit:
                raise HTTPException(503, PAUSED)
        entry = AiUsage(user_id=user_id, provider=plan.provider, model=plan.model, mode="included",
            request_id=request_id, period_key=key, reserved_credits=maximum_credits,
            credits_per_usd=s.free_ai_credits_per_usd, minimum_credits=s.free_ai_min_credits_per_request,
            task_type=task_type, reserved_tokens=maximum_input + s.free_ai_max_output_tokens,
            reserved_cost_microusd=maximum_cost, input_rate_microusd=plan.price.input_rate,
            output_rate_microusd=plan.price.output_rate, status="reserved", created_at=now)
        db.add(entry)
        db.flush()
        identifier = entry.id
        alert(db, now)
        db.commit()
        return identifier
    except BaseException:
        db.rollback()
        raise


def reconcile(db, identifier, usage=None, *, useful=False, unknown=False, latency_ms=0):
    lock(db)
    try:
        item = db.get(AiUsage, identifier, populate_existing=True)
        if item is None or item.status != "reserved":
            db.rollback()
            return
        known = usage is not None and "input_tokens" in usage and "output_tokens" in usage
        if known:
            item.input_tokens = max(0, int(usage["input_tokens"]))
            item.output_tokens = max(0, int(usage["output_tokens"]))
            item.actual_tokens = item.input_tokens + item.output_tokens
            item.actual_cost_microusd = cost(item.input_tokens, item.output_tokens,
                                            Price(item.input_rate_microusd, item.output_rate_microusd))
        else:
            item.actual_cost_microusd = item.reserved_cost_microusd if unknown or useful else 0
        requested = credits(item.actual_cost_microusd, item.credits_per_usd, item.minimum_credits) if useful else 0
        # Provider overruns are borne by EduCrea; record their entire cost, never overdraft user credits.
        item.actual_credits = min(requested, item.reserved_credits)
        if requested > item.reserved_credits or item.actual_cost_microusd > item.reserved_cost_microusd:
            logger.warning("included_ai_reservation_overrun request_id=%s", item.request_id)
        item.status = "completed" if useful else "failed"
        item.finished_at = now_utc()
        item.latency_ms = latency_ms
        alert(db, now_utc())
        db.commit()
        logger.info("included_ai_usage request_id=%s provider=%s model=%s status=%s credits=%s cost_microusd=%s latency_ms=%s",
                    item.request_id, item.provider, item.model, item.status, item.actual_credits,
                    item.actual_cost_microusd, latency_ms)
    except BaseException:
        db.rollback()
        raise


def summary(db, user_id):
    s = get_settings()
    key, start, end = period(now_utc())
    # Expire under the same lock as reservations; no provider data in the public response.
    lock(db)
    expire(db, now_utc())
    rows = list(db.scalars(select(AiUsage).where(AiUsage.mode == "included", AiUsage.user_id == user_id,
                                               AiUsage.period_key == key)))
    used = sum(map(ledger_credits, rows))
    access_status = access.status(db, user_id)
    authorized = access_status == "invited"
    available = s.free_ai_enabled and authorized
    try:
        ready = False
        for name in ("qwen", "deepseek"):
            try:
                route(name)
                ready = True
            except HTTPException:
                pass
        available = available and ready
        for begin, limit in ((start, micro_usd(s.free_ai_global_monthly_budget_usd)),
                            (now_utc().replace(hour=0, minute=0, second=0, microsecond=0),
                             micro_usd(s.free_ai_global_daily_budget_usd))):
            available = available and bool(limit) and sum(map(ledger_cost, totals(db, begin))) < limit
    except HTTPException:
        available = False
    db.commit()
    return {"enabled": s.free_ai_enabled, "available": available, "authorized": authorized,
            "access_status": access_status, "period_key": key,
            "monthly_credits_limit": s.free_ai_monthly_credits, "monthly_credits_used": used,
            "remaining_credits": max(0, s.free_ai_monthly_credits - used), "renews_at": end.isoformat()}


def history(db, user_id):
    rows = list(db.scalars(select(AiUsage).where(AiUsage.mode == "included", AiUsage.user_id == user_id)))
    periods = sorted({r.period_key for r in rows}, reverse=True)
    return [{"period_key": key, "credits_used": sum(ledger_credits(r) for r in rows if r.period_key == key)}
            for key in periods]


def metrics(db, period_key=None):
    key = period_key or period(now_utc())[0]
    rows = list(db.scalars(select(AiUsage).where(AiUsage.mode == "included", AiUsage.period_key == key)))
    users = {row.user_id for row in rows}
    used = sum(map(ledger_credits, rows))
    return {"period_key": key, "active_users": len(users), "credits_used": used,
            "average_credits_per_user": used / len(users) if users else 0,
            "estimated_cost_microusd": sum(map(ledger_cost, rows)),
            "monthly_budget_microusd": micro_usd(get_settings().free_ai_global_monthly_budget_usd),
            "monthly_budget_used_percent": (100 * sum(map(ledger_cost, rows)) /
                micro_usd(get_settings().free_ai_global_monthly_budget_usd)
                if micro_usd(get_settings().free_ai_global_monthly_budget_usd) else 0),
            "exhausted_users": sum(sum(ledger_credits(r) for r in rows if r.user_id == user) >=
                                   get_settings().free_ai_monthly_credits for user in users),
            "providers": {name: {"requests": len([r for r in rows if r.provider == name]),
                "cost_microusd": sum(ledger_cost(r) for r in rows if r.provider == name)}
                for name in ("qwen", "deepseek")},
            "errors": sum(r.status in {"failed", "expired"} for r in rows),
            "average_latency_ms": sum(r.latency_ms or 0 for r in rows) / len(rows) if rows else 0}


async def run(db, user_id, selected, prompt, finish, *, task_type="unknown", streaming=True):
    """Use the existing adapters and proposal validator. Only useful results charge user credits.

    At most one optional DeepSeek -> Qwen technical fallback, never after streamed text and never on
    authentication/configuration/validation errors. Each attempt records cost; one logical rate-limit request.
    """
    access.require_access(db, user_id)
    request_id = uuid4()
    names = [selected]
    if selected == "deepseek" and get_settings().free_ai_deepseek_fallback_to_qwen:
        names.append("qwen")
    for index, name in enumerate(names):
        plan = route(name)
        reservation = reserve(db, user_id, plan, prompt, task_type, request_id)
        usage = None
        parts = []
        started = time.monotonic()
        settled = False
        started_provider = False
        try:
            yield "status", {"stage": "generating", "provider": "educrea", "retry": index > 0}
            async with asyncio.timeout(get_settings().free_ai_request_timeout_seconds):
                provider = adapter(plan)
                started_provider = True
                if streaming:
                    response_bytes = 0
                    async for chunk in provider.stream(plan.key, plan.model, prompt):
                        if chunk.usage:
                            usage = chunk.usage
                        if chunk.text:
                            parts.append(chunk.text)
                            response_bytes += len(chunk.text.encode())
                            if response_bytes > 512 * 1024:
                                raise HTTPException(502, "La respuesta de IA EduCrea es demasiado grande.")
                            yield "token", {"text": chunk.text}
                else:
                    result = await provider.generate(plan.key, plan.model, prompt)
                    parts = [result.text]
                    usage = result.usage or None
                value = finish("".join(parts), usage or {})
            reconcile(db, reservation, usage, useful=True,
                      latency_ms=int((time.monotonic() - started) * 1000))
            settled = True
            yield "result", value
            return
        except (ProviderError, HTTPException, TimeoutError) as exc:
            reported = getattr(exc, "usage", None) or usage
            reconcile(db, reservation, reported, unknown=isinstance(exc, TimeoutError) or bool(parts)
                      or getattr(exc, "consumed_unknown", False),
                      latency_ms=int((time.monotonic() - started) * 1000))
            settled = True
            transient = isinstance(exc, TimeoutError) or (isinstance(exc, ProviderError) and exc.status_code in (429, 503, 504))
            if transient and not parts and index + 1 < len(names):
                continue
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(503 if transient else 502, "IA EduCrea no ha podido completar la generación. Inténtalo más tarde.") from None
        finally:
            if not settled:
                # Cancellation and unexpected failures release user credits, preserve unknown institutional spend.
                reconcile(db, reservation, usage, unknown=started_provider,
                          latency_ms=int((time.monotonic() - started) * 1000))


if __name__ == "__main__":
    import json
    from ...db import SessionLocal
    with SessionLocal() as session:
        print(json.dumps(metrics(session)))
