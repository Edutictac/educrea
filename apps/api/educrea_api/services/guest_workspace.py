"""Anonymous sessions reuse the ordinary project APIs and ownership checks."""
import secrets
from datetime import timezone
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select, update, delete

from ..models import User, SessionToken, Project, AiProposal, AiUsage, AiBudget, CapabilityCall
from ..models.entities import utcnow
from ..security import COOKIE_NAME, digest


def browser_guest(db, request: Request, *, csrf=False):
    token = request.cookies.get(COOKIE_NAME)
    session = db.get(SessionToken, digest(token)) if token else None
    if session is None:
        return None
    expires = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
    if expires <= utcnow() or not session.user.is_guest:
        return None
    if csrf:
        import hmac
        if not hmac.compare_digest(session.csrf_hash, digest(request.headers.get('X-CSRF-Token', ''))):
            raise HTTPException(403, 'CSRF no válido')
    return session.user


def create(db):
    identifier = uuid4()
    user = User(id=identifier, email=f'{identifier.hex}@guest.invalid', is_guest=True,
                password_hash='!guest-disabled-' + secrets.token_urlsafe(32))
    db.add(user)
    db.commit()
    return user


def adopt(db, guest_id, target):
    """Move the current browser's anonymous work, never credentials or institutional permissions.

    Caller gets guest_id only from a validated cookie or the bound SSO flow, not from client input.
    Caller owns the transaction; authenticating the destination account precedes adoption.
    """
    if guest_id is None or guest_id == target.id:
        return
    guest = db.get(User, guest_id)
    if guest is None or not guest.is_guest or target.is_guest:
        return
    from ..routers.projects import unique_slug
    for project in db.scalars(select(Project).where(Project.owner_id == guest.id).with_for_update()):
        project.slug = unique_slug(db, target.id, project.title)
        project.owner_id = target.id
        db.flush()
    for model in (AiProposal, AiUsage, CapabilityCall):
        db.execute(update(model).where(model.user_id == guest.id).values(user_id=target.id))
    # Preserve both histories; do not automatically increase the existing account's paid budget.
    guest_budget = db.get(AiBudget, guest.id)
    if guest_budget and db.get(AiBudget, target.id) is None:
        db.add(AiBudget(user_id=target.id, monthly_limit_microusd=guest_budget.monthly_limit_microusd))
    db.execute(delete(SessionToken).where(SessionToken.user_id == guest.id))
