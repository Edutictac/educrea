from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import current_user, require_csrf
from ..services import beta_admin, beta_invitations
from ..services.ai import access

router = APIRouter(prefix='/admin/beta', tags=['admin'])


class AccessInput(BaseModel):
    authorized: bool
    model_config = ConfigDict(extra='forbid')


class InviteInput(BaseModel):
    email: EmailStr
    model_config = ConfigDict(extra='forbid')


def administrator(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return beta_admin.require_role(db, user.id)


@router.get('')
def dashboard(_admin: User = Depends(administrator), db: Session = Depends(get_db)):
    return beta_admin.dashboard(db)


@router.put('/users/{user_id}/access')
def update_access(user_id: UUID, data: AccessInput, user: User = Depends(require_csrf),
                  _admin: User = Depends(administrator), db: Session = Depends(get_db)):
    return access.set_access(db, user_id, authorized=data.authorized, actor_id=user.id)


@router.post('/invitations')
def send_invitation(data: InviteInput, user: User = Depends(require_csrf),
                    _admin: User = Depends(administrator), db: Session = Depends(get_db)):
    return beta_invitations.send(db, user.id, str(data.email))


@router.post('/invitations/{invitation_id}/revoke')
def revoke_invitation(invitation_id: UUID, user: User = Depends(require_csrf),
                      _admin: User = Depends(administrator), db: Session = Depends(get_db)):
    return beta_invitations.revoke(db, user.id, invitation_id)
