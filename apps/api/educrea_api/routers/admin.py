from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import current_user, require_csrf
from ..services import beta_admin, beta_invitations
from ..services.ai import access, included, videos

router = APIRouter(prefix='/admin/beta', tags=['admin'])


class AccessInput(BaseModel):
    authorized: bool
    model_config = ConfigDict(extra='forbid')


class InviteInput(BaseModel):
    email: EmailStr
    model_config = ConfigDict(extra='forbid')


class ImageLimitsInput(BaseModel):
    weekly_limit: int = Field(ge=0)
    global_daily_limit: int = Field(ge=0)
    model_config = ConfigDict(extra='forbid')


class VideoLimitsInput(BaseModel):
    daily_limit: int = Field(ge=0)
    global_daily_limit: int = Field(ge=0)
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


@router.get('/image-limits')
def get_image_limits(_admin: User = Depends(administrator), db: Session = Depends(get_db)):
    return included.image_limits_info(db)


@router.put('/image-limits')
def update_image_limits(data: ImageLimitsInput, user: User = Depends(require_csrf),
                        _admin: User = Depends(administrator), db: Session = Depends(get_db)):
    return included.set_image_limits(db, data.weekly_limit, data.global_daily_limit, actor_id=user.id)


@router.get('/video-limits')
def get_video_limits(_admin: User = Depends(administrator), db: Session = Depends(get_db)):
    return videos.limits_info(db)


@router.put('/video-limits')
def update_video_limits(data: VideoLimitsInput, user: User = Depends(require_csrf),
                        _admin: User = Depends(administrator), db: Session = Depends(get_db)):
    return videos.set_limits(db, data.daily_limit, data.global_daily_limit, actor_id=user.id)
