"""Per-account institutional AI beta access. Personal API keys are outside this permission.

The first beta uses server-side grants to existing accounts, avoiding transferable invitation tokens,
public administration endpoints and changes to registration or SSO.
"""
import argparse
import json
import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import IncludedAiAccess, IncludedAiWaitlist, User
from ...models.entities import utcnow

INVITATION_REQUIRED = ("IA EduCrea está en beta por invitación. Tu cuenta no tiene acceso. "
                       "Puedes seguir usando tu propia API sin invitación.")
logger = logging.getLogger(__name__)


def status(db: Session, user_id: UUID) -> str:
    user = db.get(User, user_id)
    if user is None or user.is_guest:
        return "not_invited"
    grant = db.get(IncludedAiAccess, user_id, populate_existing=True)
    if grant is None:
        return "not_invited"
    if grant.revoked_at is not None:
        return "revoked"
    return "invited" if grant.granted_at is not None else "not_invited"


def require_access(db: Session, user_id: UUID) -> None:
    if status(db, user_id) != "invited":
        raise HTTPException(403, INVITATION_REQUIRED)


def apply_access(db: Session, user_id: UUID, *, authorized: bool) -> dict:
    """Update permission inside a caller-owned transaction (caller must hold the shared lock)."""
    user = db.get(User, user_id)
    if user is None or user.is_guest:
        raise HTTPException(404, "Cuenta registrada no encontrada")
    grant = db.get(IncludedAiAccess, user_id, populate_existing=True)
    if grant is None:
        grant = IncludedAiAccess(user_id=user_id)
        db.add(grant)
    now = utcnow()
    if authorized:
        if grant.granted_at is None or grant.revoked_at is not None:
            grant.granted_at = now
        grant.revoked_at = None
    elif grant.revoked_at is None:
        grant.revoked_at = now
    request = db.get(IncludedAiWaitlist, user_id, populate_existing=True)
    if request is not None:
        request.status = "accepted" if authorized else "closed"
        request.updated_at = now
    return {"user_id": str(user_id), "access_status": "invited" if authorized else "revoked"}


def set_access(db: Session, user_id: UUID, *, authorized: bool, actor_id: UUID | None = None) -> dict:
    from .included import lock
    from ...models import BetaAdminAudit
    lock(db)
    try:
        if actor_id is not None:
            from ..beta_admin import require_role
            require_role(db, actor_id)
        result = apply_access(db, user_id, authorized=authorized)
        db.add(BetaAdminAudit(actor_id=actor_id, target_user_id=user_id,
                              action="access_granted" if authorized else "access_revoked"))
        # Revoke outstanding email invitations too, so another SSO login cannot undo revocation.
        if not authorized:
            from ...models import BetaInvitation
            email = db.get(User, user_id).email
            for invitation in db.scalars(select(BetaInvitation).where(BetaInvitation.email == email)):
                invitation.state = "revoked"
                invitation.updated_at = utcnow()
        db.commit()
        logger.info("included_ai_access_changed user_id=%s status=%s", user_id, result["access_status"])
        return result
    except BaseException:
        db.rollback()
        raise


def waitlist_status(db: Session, user_id: UUID) -> dict:
    entry = db.get(IncludedAiWaitlist, user_id, populate_existing=True)
    if entry is None:
        return {"status": "none"}
    return {"status": entry.status, "teaching_context": entry.teaching_context,
            "intended_use": entry.intended_use, "requested_at": entry.created_at.isoformat()}


def join_waitlist(db: Session, user_id: UUID, teaching_context: str, intended_use: str) -> dict:
    from .included import lock
    lock(db)
    try:
        if db.get(User, user_id) is None:
            raise HTTPException(401, "Sesión no válida")
        if db.get(User, user_id).is_guest:
            raise HTTPException(403, "Regístrate para solicitar acceso a la beta de IA EduCrea")
        if status(db, user_id) == "invited":
            raise HTTPException(409, "Tu cuenta ya tiene acceso a IA EduCrea")
        entry = db.get(IncludedAiWaitlist, user_id, populate_existing=True)
        if entry is None:
            entry = IncludedAiWaitlist(user_id=user_id)
            db.add(entry)
        entry.status = "pending"
        entry.teaching_context = teaching_context
        entry.intended_use = intended_use
        entry.updated_at = utcnow()
        db.commit()
        return waitlist_status(db, user_id)
    except BaseException:
        db.rollback()
        raise


def waiting_accounts(db: Session, user_id: UUID | None = None, limit: int = 50) -> list[dict]:
    query = select(IncludedAiWaitlist)
    if user_id is None:
        query = query.where(IncludedAiWaitlist.status == "pending")
    else:
        query = query.where(IncludedAiWaitlist.user_id == user_id)
    rows = db.scalars(query.order_by(IncludedAiWaitlist.created_at, IncludedAiWaitlist.user_id).limit(limit))
    return [{"user_id": str(row.user_id), "status": row.status, "teaching_context": row.teaching_context,
             "intended_use": row.intended_use, "requested_at": row.created_at.isoformat()} for row in rows]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gestionar invitaciones de IA EduCrea desde el servidor")
    parser.add_argument("action", choices=("grant", "revoke", "status", "waitlist"))
    account = parser.add_mutually_exclusive_group()
    account.add_argument("--user-id", type=UUID)
    account.add_argument("--email")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)
    if args.action != "waitlist" and not (args.user_id or args.email):
        parser.error("Indica --user-id o --email")
    if not 1 <= args.limit <= 500:
        parser.error("El límite debe estar entre 1 y 500")
    from ...db import SessionLocal
    with SessionLocal() as db:
        user_id = args.user_id
        if args.email:
            user_id = db.scalar(select(User.id).where(User.email == args.email.strip().lower()))
        if user_id is None and (args.action != "waitlist" or args.email):
            parser.exit(1, "Cuenta no encontrada. La persona debe registrarse primero.\n")
        try:
            if args.action == "waitlist":
                result = waiting_accounts(db, user_id, args.limit)
            elif args.action == "status":
                if db.get(User, user_id) is None:
                    raise HTTPException(404, "Cuenta no encontrada")
                result = {"user_id": str(user_id), "access_status": status(db, user_id)}
            else:
                result = set_access(db, user_id, authorized=args.action == "grant")
        except HTTPException as exc:
            parser.exit(1, str(exc.detail) + "\n")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
