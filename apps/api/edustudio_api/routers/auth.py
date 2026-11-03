import secrets

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import SessionToken, User
from ..schemas import Credentials, SessionOut, UserOut
from ..security import COOKIE_NAME, current_session, digest, hash_password, new_session, require_csrf, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def set_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=get_settings().cookie_secure,
                        samesite="strict", max_age=get_settings().session_days * 86400, path="/")


@router.post("/register", response_model=SessionOut, status_code=201)
def register(data: Credentials, response: Response, db: Session = Depends(get_db)) -> SessionOut:
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Correo ya registrado")
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token, csrf = new_session(db, user)
    set_cookie(response, token)
    return SessionOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/login", response_model=SessionOut)
def login(data: Credentials, response: Response, db: Session = Depends(get_db)) -> SessionOut:
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or not verify_password(user.password_hash, data.password):
        raise HTTPException(401, "Credenciales no válidas")
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

