"""Administration is an explicit account role, never inferred from an email supplied at signup."""
import argparse
import json
from uuid import UUID
from sqlalchemy import select
from fastapi import HTTPException

from ..models import User, IncludedAiWaitlist, IncludedAiAccess, BetaAdminAudit, BetaInvitation
from .ai import access, included, videos
from . import beta_mail


def require_role(db, user_id):
    user = db.get(User, user_id, populate_existing=True)
    if user is None or user.is_guest or not user.is_admin:
        raise HTTPException(403, 'Acceso restringido a administración')
    return user


def dashboard(db, limit=100):
    waiting = []
    query = select(IncludedAiWaitlist, User).join(User, User.id == IncludedAiWaitlist.user_id).where(
        IncludedAiWaitlist.status == 'pending').order_by(IncludedAiWaitlist.created_at).limit(limit)
    for request, user in db.execute(query):
        waiting.append({'user_id': str(user.id), 'email': user.email, 'teaching_context': request.teaching_context,
                        'intended_use': request.intended_use, 'requested_at': request.created_at.isoformat()})
    guests = [{'user_id': str(user.id), 'email': user.email, 'access_status': 'revoked' if grant.revoked_at else 'invited'}
              for grant, user in db.execute(select(IncludedAiAccess, User).join(User).order_by(
                  IncludedAiAccess.granted_at.desc()).limit(limit))]
    invites = [invitation_out(i) for i in db.scalars(select(BetaInvitation).order_by(
        BetaInvitation.created_at.desc()).limit(limit))]
    return {'waitlist': waiting, 'guests': guests, 'invitations': invites,
            'mail_ready': beta_mail.ready(), 'metrics': included.metrics(db),
            'image_limits': included.image_limits_info(db), 'video_limits': videos.limits_info(db)}


def invitation_out(item):
    expires = item.expires_at.replace(tzinfo=included.timezone.utc) if item.expires_at.tzinfo is None else item.expires_at
    state = 'expired' if item.state == 'sent' and expires <= included.now_utc() else item.state
    return {'id': str(item.id), 'email': item.email, 'state': state,
            'expires_at': item.expires_at.isoformat(), 'sent_at': item.sent_at.isoformat() if item.sent_at else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Conceder o revocar administración desde el servidor')
    parser.add_argument('action', choices=('grant', 'revoke'))
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument('--user-id', type=UUID)
    identity.add_argument('--email')
    args = parser.parse_args(argv)
    from ..db import SessionLocal
    with SessionLocal() as db:
        user_id = args.user_id
        if args.email:
            user_id = db.scalar(select(User.id).where(User.email == args.email.strip().lower()))
        included.lock(db)
        user = db.get(User, user_id) if user_id else None
        if user is None or user.is_guest:
            parser.exit(1, 'Cuenta no encontrada. Debe existir previamente.\n')
        user.is_admin = args.action == 'grant'
        db.add(BetaAdminAudit(target_user_id=user.id, action='admin_granted' if user.is_admin else 'admin_revoked'))
        db.commit()
        print(json.dumps({'user_id': str(user.id), 'is_admin': user.is_admin}))


if __name__ == '__main__':
    main()
