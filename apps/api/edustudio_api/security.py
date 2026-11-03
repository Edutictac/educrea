import hashlib
import hmac
import secrets
from datetime import timedelta, timezone

from argon2 import PasswordHasher, exceptions
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import SessionToken, User
from .models.entities import utcnow

hasher = PasswordHasher()
COOKIE_NAME = "edustudio_session"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (exceptions.VerifyMismatchError, exceptions.VerificationError, exceptions.InvalidHashError):
        return False


def new_session(db: Session, user: User) -> tuple[str, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(SessionToken(token_hash=digest(token), csrf_hash=digest(csrf), user_id=user.id,
                        expires_at=utcnow() + timedelta(days=get_settings().session_days)))
    db.commit()
    return token, csrf


def current_session(request: Request, db: Session = Depends(get_db)) -> SessionToken:
    token = request.cookies.get(COOKIE_NAME)
    session = db.get(SessionToken, digest(token)) if token else None
    expires_at = session.expires_at if session is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if session is None or expires_at <= utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida")
    return session


def current_user(session: SessionToken = Depends(current_session)) -> User:
    return session.user


def require_csrf(request: Request, session: SessionToken = Depends(current_session)) -> User:
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not hmac.compare_digest(digest(supplied), session.csrf_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF no válido")
    return session.user

