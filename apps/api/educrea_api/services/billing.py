"""Minimal Stripe REST adapter using existing httpx; sandbox payments only."""
import hashlib
import hmac
import json
import time
from datetime import timezone
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import TestTopup, TestWalletEntry, User
from ..models.entities import utcnow

EVENTS = {"checkout.session.completed", "checkout.session.async_payment_succeeded",
          "checkout.session.async_payment_failed", "checkout.session.expired"}


def configuration():
    settings = get_settings()
    key = settings.stripe_secret_key.get_secret_value() if settings.stripe_secret_key else ""
    secret = settings.stripe_webhook_secret.get_secret_value() if settings.stripe_webhook_secret else ""
    base = settings.public_base_url.rstrip("/")
    url = urlsplit(base)
    local = url.hostname in {"localhost", "127.0.0.1", "::1"}
    valid_url = (url.scheme == "https" or (settings.allow_insecure_urls and local and url.scheme == "http"))
    if (not settings.stripe_test_enabled or not key.startswith(("sk_test_", "rk_test_"))
            or not secret.startswith("whsec_") or not valid_url or not url.hostname
            or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}):
        raise HTTPException(503, "Recargas de prueba no disponibles")
    return key, secret, base


def registered(user: User):
    if user.is_guest:
        raise HTTPException(403, "Las recargas requieren una cuenta")


def wallet(db: Session, user: User):
    registered(user)
    try:
        configuration()
        enabled = True
    except HTTPException:
        enabled = False
    total = db.scalar(select(func.coalesce(func.sum(TestWalletEntry.amount_microeur), 0))
                      .where(TestWalletEntry.user_id == user.id))
    entries = db.scalars(select(TestWalletEntry).where(TestWalletEntry.user_id == user.id)
                        .order_by(TestWalletEntry.created_at.desc(), TestWalletEntry.id).limit(50))
    attempts = db.scalars(select(TestTopup).where(TestTopup.user_id == user.id)
                         .order_by(TestTopup.created_at.desc(), TestTopup.id).limit(20))
    return {"enabled": enabled, "livemode": False, "currency": "eur", "balance_microeur": total,
            "entries": [{"id": str(e.id), "amount_microeur": e.amount_microeur,
                         "created_at": e.created_at.isoformat()} for e in entries],
            "topups": [{"id": str(t.id), "state": t.state} for t in attempts]}


def stripe_create(key: str, attempt: TestTopup) -> dict:
    data = {
        # Let the sandbox's payment-method configuration determine available methods.
        "mode": "payment",
        "line_items[0][price_data][currency]": "eur",
        "line_items[0][price_data][unit_amount]": "1000",
        "line_items[0][price_data][product_data][name]": "EduCrea · saldo de prueba",
        "line_items[0][quantity]": "1",
        "client_reference_id": str(attempt.id), "metadata[educrea_topup_id]": str(attempt.id),
        "metadata[educrea_scope]": "wallet_test_v1",
        "success_url": f"{attempt.return_base}/saldo?checkout=returned",
        "cancel_url": f"{attempt.return_base}/saldo?checkout=cancelled",
        "adaptive_pricing[enabled]": "false",
    }
    try:
        # Fixed destination; never use user-provided URLs, log payloads, or expose Stripe errors/keys.
        response = httpx.post("https://api.stripe.com/v1/checkout/sessions", data=data,
                              headers={"Authorization": f"Bearer {key}",
                                       "Idempotency-Key": f"educrea-test-topup-{attempt.id}"},
                              timeout=20, follow_redirects=False)
        response.raise_for_status()
        result = response.json()
        checkout = urlsplit(result.get("url", ""))
        if (result.get("livemode") is not False or not result.get("id", "").startswith("cs_test_")
                or checkout.scheme != "https" or checkout.netloc != "checkout.stripe.com"):
            raise ValueError("Invalid sandbox Checkout")
        return result
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise HTTPException(502, "No se pudo abrir Stripe. Reintenta la misma recarga") from None


def checkout(db: Session, user: User, request_id: UUID):
    registered(user)
    key, _secret, base = configuration()
    query = select(TestTopup).where(TestTopup.user_id == user.id, TestTopup.request_id == request_id)
    attempt = db.scalar(query)
    if attempt is None:
        attempt = TestTopup(user_id=user.id, request_id=request_id, return_base=base)
        db.add(attempt)
        try:
            db.commit()  # Persist before the network request: retries reuse the same Stripe key.
        except IntegrityError:
            db.rollback()
            attempt = db.scalar(query)
            if attempt is None:
                raise
    if attempt.state in {"paid", "failed", "expired"}:
        raise HTTPException(409, "Esta recarga ya ha terminado")
    if attempt.checkout_url:
        return {"url": attempt.checkout_url, "topup_id": str(attempt.id)}
    created = attempt.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    # Stripe retains idempotency keys for >=24h; do not recreate an uncertain payment after that window.
    if (utcnow() - created).total_seconds() >= 23 * 3600:
        raise HTTPException(409, "Esta recarga requiere revisión antes de reintentarse")
    result = stripe_create(key, attempt)
    db.execute(update(TestTopup).where(TestTopup.id == attempt.id, TestTopup.session_id.is_(None))
               .values(session_id=result["id"], checkout_url=result["url"]))
    db.execute(update(TestTopup).where(TestTopup.id == attempt.id, TestTopup.state == "creating")
               .values(state="pending"))
    db.commit()
    return {"url": result["url"], "topup_id": str(attempt.id)}


def verified_event(payload: bytes, signature: str, secret: str):
    try:
        parts = [part.split("=", 1) for part in signature.split(",")]
        timestamp = next(value for name, value in parts if name == "t")
        if abs(time.time() - int(timestamp)) > 300:
            raise ValueError()
        expected = hmac.new(secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, value) for name, value in parts if name == "v1"):
            raise ValueError()
        event = json.loads(payload)
        if not isinstance(event, dict):
            raise ValueError()
        return event
    except (ValueError, StopIteration, TypeError):
        raise HTTPException(400, "Webhook no válido") from None


def fulfill(db: Session, event: dict):
    if event.get("livemode") is not False:
        raise HTTPException(400, "Solo se admiten eventos de prueba")
    kind = event.get("type")
    if not isinstance(kind, str):
        raise HTTPException(400, "Tipo de evento no válido")
    if kind not in EVENTS:
        return
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(obj, dict):
        raise HTTPException(400, "Objeto de evento no válido")
    metadata = obj.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise HTTPException(400, "Metadatos no válidos")
    if metadata.get("educrea_scope") != "wallet_test_v1":
        return  # Other products on this Stripe account are not this wallet.
    try:
        attempt_id = UUID(metadata.get("educrea_topup_id", ""))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, "Referencia de recarga no válida") from None
    attempt = db.get(TestTopup, attempt_id)
    if attempt is None:
        raise HTTPException(400, "Recarga no encontrada")
    session_id = obj.get("id", "")
    if (obj.get("livemode") is not False or obj.get("mode") != "payment"
            or not isinstance(session_id, str) or not session_id.startswith("cs_test_") or obj.get("currency") != "eur"
            or type(obj.get("amount_total")) is not int or obj["amount_total"] != 1000
            or obj.get("client_reference_id") != str(attempt.id)
            or (attempt.session_id is not None and attempt.session_id != session_id)):
        raise HTTPException(400, "El pago no corresponde a la recarga")
    paid = kind in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
    if paid and (obj.get("payment_status") != "paid" or obj.get("status") != "complete"):
        return
    state = "paid" if paid else ("expired" if kind.endswith("expired") else "failed")
    # Conditional write serializes concurrent deliveries on PostgreSQL/SQLite. The entry and
    # state transition commit together; UNIQUE(topup_id) is a second line of protection.
    claimed = db.execute(update(TestTopup).where(TestTopup.id == attempt.id, TestTopup.state != "paid",
                         (TestTopup.session_id.is_(None) | (TestTopup.session_id == session_id)))
                         .values(state=state, session_id=session_id).returning(TestTopup.id)).scalar_one_or_none()
    if claimed is not None and paid:
        db.add(TestWalletEntry(user_id=attempt.user_id, topup_id=attempt.id, amount_microeur=10_000_000))
    db.commit()
