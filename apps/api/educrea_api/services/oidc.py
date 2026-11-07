"""OpenID Connect login (authorization code + PKCE, confidential client).

Security notes:
- The browser is bound to the flow by a random cookie whose hash keys a server-side record (state, nonce, PKCE
  verifier, return path): this prevents login CSRF and code injection.
- The ID token signature, issuer, audience, expiry and nonce are verified against the provider's JWKS.
- `next` must be a same-site relative path (no open redirect).
- Linking an existing local account by e-mail needs `email_verified`; the old password is then disabled so a
  pre-registered account (registration is open) cannot be used to hijack the identity.
"""

import base64
import hashlib
import secrets
import time
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import OidcFlow, OidcIdentity, SessionToken, User
from ..models.entities import utcnow
from ..security import digest, hash_password

FLOW_MINUTES = 10
_cache: dict[str, tuple[float, dict]] = {}


def enabled() -> bool:
    settings = get_settings()
    return bool(settings.oidc_issuer and settings.oidc_client_id and settings.oidc_client_secret
                and settings.oidc_redirect_uri)


def http_client() -> httpx.Client:  # replaced in tests
    return httpx.Client(timeout=10, follow_redirects=False)


def _get_json(url: str, ttl: int = 600) -> dict:
    cached = _cache.get(url)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    try:
        with http_client() as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "No se pudo contactar con el proveedor de identidad") from exc
    _cache[url] = (time.monotonic() + ttl, data)
    return data


def discovery() -> dict:
    issuer = get_settings().oidc_issuer.rstrip("/")
    data = _get_json(f"{issuer}/.well-known/openid-configuration")
    if data.get("issuer", "").rstrip("/") != issuer:
        raise HTTPException(502, "El proveedor de identidad declara un emisor distinto")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not str(data.get(key, "")).startswith("https://") and not str(data.get(key, "")).startswith("http://localhost"):
            raise HTTPException(502, "Configuración del proveedor de identidad no válida")
    return data


def safe_next(value: str | None) -> str:
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value and len(value) <= 300:
        return value
    return "/projects"


def begin(db: Session, next_path: str | None) -> tuple[str, str]:
    """Returns (authorization URL, browser cookie value)."""
    settings = get_settings()
    meta = discovery()
    cookie, state, nonce = (secrets.token_urlsafe(32) for _ in range(3))
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    db.execute(delete(OidcFlow).where(OidcFlow.expires_at < utcnow()))
    db.add(OidcFlow(cookie_hash=digest(cookie), state=state, nonce=nonce, verifier=verifier,
                    next_path=safe_next(next_path), expires_at=utcnow() + timedelta(minutes=FLOW_MINUTES)))
    db.commit()
    query = urlencode({"response_type": "code", "client_id": settings.oidc_client_id,
                       "redirect_uri": settings.oidc_redirect_uri, "scope": settings.oidc_scopes, "state": state,
                       "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"})
    return f"{meta['authorization_endpoint']}?{query}", cookie


def finish(db: Session, cookie: str | None, state: str, code: str) -> tuple[User, str]:
    """Validates the callback and returns (local user, return path)."""
    settings = get_settings()
    flow = db.get(OidcFlow, digest(cookie)) if cookie else None
    if flow is None:
        raise HTTPException(400, "Inicio de sesión caducado o no iniciado en este navegador")
    expires = flow.expires_at if flow.expires_at.tzinfo else flow.expires_at.replace(tzinfo=utcnow().tzinfo)
    valid = secrets.compare_digest(flow.state, state) and expires > utcnow()
    nonce, verifier, next_path = flow.nonce, flow.verifier, flow.next_path
    db.delete(flow)  # one use only
    db.commit()
    if not valid:
        raise HTTPException(400, "Inicio de sesión caducado o no válido")
    meta = discovery()
    try:
        with http_client() as client:
            response = client.post(meta["token_endpoint"], data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": settings.oidc_redirect_uri,
                "client_id": settings.oidc_client_id, "code_verifier": verifier},
                auth=(settings.oidc_client_id, settings.oidc_client_secret.get_secret_value()))
        response.raise_for_status()
        id_token = response.json()["id_token"]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(502, "El proveedor de identidad rechazó el inicio de sesión") from exc
    claims = _verify_id_token(id_token, meta, nonce)
    return _user_for(db, settings.oidc_issuer.rstrip("/"), claims), next_path


def _verify_id_token(token: str, meta: dict, nonce: str) -> dict:
    settings = get_settings()
    try:
        keys = KeySet.import_key_set(_get_json(meta["jwks_uri"]))
        decoded = jwt.decode(token, keys, algorithms=["RS256", "ES256", "PS256"])
        jwt.JWTClaimsRegistry(leeway=60, iss={"essential": True, "value": meta["issuer"]},
                              aud={"essential": True, "value": settings.oidc_client_id},
                              exp={"essential": True}, sub={"essential": True}).validate(decoded.claims)
        claims = decoded.claims
    except (JoseError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(401, "Identidad no válida") from exc
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise HTTPException(401, "Identidad no válida")
    return dict(claims)


def _user_for(db: Session, issuer: str, claims: dict) -> User:
    subject = str(claims["sub"])[:255]
    email = str(claims.get("email", "")).strip().lower()
    identity = db.scalar(select(OidcIdentity).where(OidcIdentity.issuer == issuer, OidcIdentity.subject == subject))
    if identity is not None:
        return db.get(User, identity.user_id)
    if not email or claims.get("email_verified") is False:
        raise HTTPException(403, "Tu cuenta de identidad no tiene un correo verificado")
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(secrets.token_urlsafe(48)))  # unusable local password
        db.add(user)
        db.flush()
    elif get_settings().oidc_link_by_email:
        # The local account may have been registered by someone else with this address: cut its password and sessions.
        user.password_hash = hash_password(secrets.token_urlsafe(48))
        db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    else:
        raise HTTPException(409, "Ya existe una cuenta local con ese correo")
    db.add(OidcIdentity(user_id=user.id, issuer=issuer, subject=subject, email=email))
    db.commit()
    return user
