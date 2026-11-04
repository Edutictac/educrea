from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..security import new_session
from ..services import oidc
from .auth import set_cookie

router = APIRouter(prefix="/auth", tags=["auth"])
FLOW_COOKIE = "edustudio_oidc_flow"


@router.get("/config")
def auth_config() -> dict:
    return {"oidc_enabled": oidc.enabled(), "local_auth_enabled": get_settings().local_auth_enabled}


@router.get("/oidc/login")
def oidc_login(next: str | None = Query(default=None, max_length=300), db: Session = Depends(get_db)):
    if not oidc.enabled():
        raise HTTPException(404, "El inicio de sesión único no está configurado")
    url, cookie = oidc.begin(db, next)
    response = RedirectResponse(url, status_code=303)
    # Lax: the callback is a cross-site top-level navigation coming back from the identity provider.
    response.set_cookie(FLOW_COOKIE, cookie, httponly=True, secure=get_settings().cookie_secure, samesite="lax",
                        max_age=oidc.FLOW_MINUTES * 60, path="/api/auth/oidc")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/oidc/callback")
def oidc_callback(request: Request, code: str = Query(default="", max_length=2048),
                  state: str = Query(default="", max_length=256), error: str = Query(default="", max_length=100),
                  db: Session = Depends(get_db)):
    if not oidc.enabled():
        raise HTTPException(404, "El inicio de sesión único no está configurado")
    if error or not code or not state:
        raise HTTPException(400, "El proveedor de identidad canceló o rechazó el inicio de sesión")
    user, next_path = oidc.finish(db, request.cookies.get(FLOW_COOKIE), state, code)
    token, _csrf = new_session(db, user)
    response = RedirectResponse(next_path, status_code=303)
    set_cookie(response, token)
    response.delete_cookie(FLOW_COOKIE, path="/api/auth/oidc")
    response.headers["Cache-Control"] = "no-store"
    return response
