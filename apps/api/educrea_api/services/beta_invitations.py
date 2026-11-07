"""Email-specific invitations, redeemed only by a verified SSO email. No bearer tokens."""
from datetime import timedelta
from sqlalchemy import select, func
from fastapi import HTTPException

from ..config import get_settings
from ..models import BetaInvitation, BetaAdminAudit, User
from .ai import included, access
from .beta_admin import require_role, invitation_out
from . import beta_mail

SEND_ACTIONS = ('invitation_requested', 'invitation_sent', 'invitation_failed')


def send(db, actor_id, email):
    require_role(db, actor_id)
    beta_mail.configuration()  # Fail before reserving delivery or changing any access.
    s = get_settings()
    email = email.strip().lower()
    included.lock(db)
    try:
        require_role(db, actor_id)
        now = included.now_utc()
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        count = db.scalar(select(func.count()).select_from(BetaAdminAudit).where(
            BetaAdminAudit.action.in_(SEND_ACTIONS), BetaAdminAudit.created_at >= since))
        if count >= s.beta_invitation_daily_limit:
            raise HTTPException(429, 'Se ha alcanzado el límite diario de invitaciones')
        item = db.scalar(select(BetaInvitation).where(BetaInvitation.email == email))
        if item:
            if item.state == 'accepted':
                raise HTTPException(409, 'La invitación ya fue aceptada; gestiona el acceso de la cuenta')
            updated = item.updated_at.replace(tzinfo=included.timezone.utc) if item.updated_at.tzinfo is None else item.updated_at
            if (now - updated).total_seconds() < s.beta_invitation_cooldown_seconds:
                raise HTTPException(429, 'Espera unos minutos antes de volver a invitar a este correo')
        else:
            item = BetaInvitation(email=email)
            db.add(item)
        item.state = 'sending'
        item.created_by = actor_id
        item.accepted_by = None
        item.sent_at = None
        item.updated_at = now
        item.expires_at = now + timedelta(days=s.beta_invitation_days)
        db.flush()
        attempt = BetaAdminAudit(actor_id=actor_id, invitation_id=item.id, action='invitation_requested')
        db.add(attempt)
        db.flush()
        invitation_id, attempt_id = item.id, attempt.id
        db.commit()
    except BaseException:
        db.rollback()
        raise
    failed = False
    try:
        beta_mail.send_invitation(email, s.beta_invitation_days)
    except HTTPException:
        failed = True
    included.lock(db)
    try:
        item = db.get(BetaInvitation, invitation_id, populate_existing=True)
        attempt = db.get(BetaAdminAudit, attempt_id, populate_existing=True)
        attempt.action = 'invitation_failed' if failed else 'invitation_sent'
        if item.state == 'sending':
            item.state = 'failed' if failed else 'sent'
            item.sent_at = None if failed else included.now_utc()
            item.updated_at = included.now_utc()
        db.commit()
        result = invitation_out(item)
    except BaseException:
        db.rollback()
        raise
    if failed:
        raise HTTPException(503, 'El servidor de correo no aceptó la invitación. Puedes volver a intentarlo más tarde.')
    return result


def revoke(db, actor_id, invitation_id):
    included.lock(db)
    try:
        require_role(db, actor_id)
        item = db.get(BetaInvitation, invitation_id, populate_existing=True)
        if item is None:
            raise HTTPException(404, 'Invitación no encontrada')
        item.state = 'revoked'
        item.updated_at = included.now_utc()
        if item.accepted_by is not None and db.get(User, item.accepted_by):
            access.apply_access(db, item.accepted_by, authorized=False)
        db.add(BetaAdminAudit(actor_id=actor_id, invitation_id=item.id, target_user_id=item.accepted_by,
                              action='invitation_revoked'))
        db.commit()
        return invitation_out(item)
    except BaseException:
        db.rollback()
        raise


def claim_verified(db, user_id, verified_email):
    # Called exclusively after cryptographic verification of a live SSO ID token with email_verified=true.
    email = verified_email.strip().lower()
    candidate = db.scalar(select(BetaInvitation.id).where(BetaInvitation.email == email, BetaInvitation.state == 'sent'))
    if candidate is None:
        return
    included.lock(db)
    try:
        user = db.get(User, user_id, populate_existing=True)
        item = db.get(BetaInvitation, candidate, populate_existing=True)
        now = included.now_utc()
        expiry = item.expires_at.replace(tzinfo=included.timezone.utc) if item.expires_at.tzinfo is None else item.expires_at
        if not user or user.email != email or item.state != 'sent' or expiry <= now:
            db.rollback()
            return
        access.apply_access(db, user_id, authorized=True)
        item.state = 'accepted'
        item.accepted_by = user_id
        item.updated_at = now
        db.add(BetaAdminAudit(target_user_id=user_id, invitation_id=item.id, action='invitation_accepted'))
        db.commit()
    except BaseException:
        db.rollback()
        raise
