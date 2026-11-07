import secrets

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import SessionToken, User
from ..schemas import Credentials, SessionOut, UserOut
from ..services import guest_workspace
from ..security import COOKIE_NAME, current_session, digest, hash_password, new_session, require_csrf, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def set_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=get_settings().cookie_secure,
                        samesite="strict", max_age=get_settings().session_days * 86400, path="/")


@router.post("/guest", response_model=SessionOut)
def open_workspace(request: Request, response: Response, db: Session = Depends(get_db)) -> SessionOut:
    # Browser bootstrap only establishes an isolated workspace; it never assigns registered privileges.
    from urllib.parse import urlsplit
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        raise HTTPException(403, "Origen no permitido")
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc != request.headers.get("Host"):
        raise HTTPException(403, "Origen no permitido")
    token = request.cookies.get(COOKIE_NAME)
    existing = db.get(SessionToken, digest(token)) if token else None
    if existing:
        from datetime import timezone
        expires = existing.expires_at.replace(tzinfo=timezone.utc) if existing.expires_at.tzinfo is None else existing.expires_at
        from ..models.entities import utcnow
        if expires > utcnow():
            csrf = secrets.token_urlsafe(32)
            existing.csrf_hash = digest(csrf)
            db.commit()
            response.headers['Cache-Control'] = 'no-store'
            return SessionOut(user=UserOut.model_validate(existing.user), csrf_token=csrf)
    user = guest_workspace.create(db)
    token, csrf = new_session(db, user)
    set_cookie(response, token)
    response.headers['Cache-Control'] = 'no-store'
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/register", response_model=SessionOut, status_code=201)
def register(data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)) -> SessionOut:
    if not get_settings().local_auth_enabled:
        raise HTTPException(403, "El registro local está desactivado: usa el inicio de sesión único")
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Correo ya registrado")
    guest = guest_workspace.browser_guest(db, request, csrf=True)
    user = guest or User(email=email, password_hash="")
    user.email = email
    user.password_hash = hash_password(data.password)
    user.is_guest = False
    if guest:
        from sqlalchemy import delete
        db.execute(delete(SessionToken).where(SessionToken.user_id == guest.id))
    db.add(user)
    db.commit()
    db.refresh(user)
    token, csrf = new_session(db, user)
    set_cookie(response, token)
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/login", response_model=SessionOut)
def login(data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)) -> SessionOut:
    if not get_settings().local_auth_enabled:
        raise HTTPException(403, "El acceso local está desactivado: usa el inicio de sesión único")
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or user.is_guest or not verify_password(user.password_hash, data.password):
        raise HTTPException(401, "Credenciales no válidas")
    guest = guest_workspace.browser_guest(db, request, csrf=True)
    if guest:
        guest_workspace.adopt(db, guest.id, user)
        db.commit()
    token, csrf = new_session(db, user)
    set_cookie(response, token)
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.get("/me", response_model=SessionOut)
def me(session: SessionToken = Depends(current_session), db: Session = Depends(get_db)) -> SessionOut:
    csrf = secrets.token_urlsafe(32)
    session.csrf_hash = digest(csrf)
    db.commit()
    return SessionOut(user=UserOut.model_validate(session.user), csrf_token=csrf)


@router.post("/logout", status_code=204)
def logout(response: Response, session: SessionToken = Depends(current_session),
           _user: User = Depends(require_csrf), db: Session = Depends(get_db)) -> None:
    db.delete(session)
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/")

