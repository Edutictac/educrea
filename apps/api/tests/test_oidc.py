import json
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey
from fastapi.testclient import TestClient
from pydantic import SecretStr

from educrea_api.config import get_settings
from educrea_api.services import oidc
from test_auth_projects import register

ISSUER = "https://id.example.org/application/o/educrea/"
CLIENT = "educrea.example.org"
KEY = RSAKey.generate_key(2048, parameters={"kid": "k1"})
ROGUE = RSAKey.generate_key(2048, parameters={"kid": "k1"})
signing = {"key": KEY}
claims_for_next: dict = {}


def idp_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/.well-known/openid-configuration"):
        return httpx.Response(200, json={"issuer": ISSUER, "authorization_endpoint": "https://id.example.org/authorize/",
                                          "token_endpoint": "https://id.example.org/token/", "jwks_uri": "https://id.example.org/jwks/"})
    if path == "/jwks/":
        return httpx.Response(200, json={"keys": [KEY.as_dict(private=False)]})
    if path == "/token/":
        form = parse_qs(request.content.decode())
        assert form["code_verifier"] and form["grant_type"] == ["authorization_code"]
        assert request.headers["authorization"].startswith("Basic ")
        if form["code"] == ["bad"]:
            return httpx.Response(400, json={"error": "invalid_grant"})
        now = int(time.time())
        body = {"iss": ISSUER, "aud": CLIENT, "iat": now, "exp": now + 300, **claims_for_next}
        token = jwt.encode({"alg": "RS256", "kid": "k1"}, body, signing["key"])
        return httpx.Response(200, json={"id_token": token, "access_token": "x"})
    return httpx.Response(404)


@pytest.fixture
def sso(monkeypatch):
    settings = get_settings()
    for name, value in {"oidc_issuer": ISSUER, "oidc_client_id": CLIENT, "oidc_redirect_uri": "https://app.example.org/api/auth/oidc/callback",
                        "oidc_client_secret": SecretStr("test-secret")}.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(oidc, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(idp_handler)))
    oidc._cache.clear()
    claims_for_next.clear()
    signing["key"] = KEY


def start(client: TestClient, next_path="/projects"):
    response = client.get("/api/auth/oidc/login", params={"next": next_path}, follow_redirects=False)
    assert response.status_code == 303
    query = parse_qs(urlparse(response.headers["location"]).query)
    return query, response


def login_as(client, sub="u1", email="Teacher@Example.org", **extra):
    query, _ = start(client)
    claims_for_next.update({"sub": sub, "email": email, "email_verified": True, "nonce": query["nonce"][0], **extra})
    return client.get("/api/auth/oidc/callback", params={"code": "ok", "state": query["state"][0]}, follow_redirects=False)


def test_disabled_by_default_and_config(client: TestClient):
    assert client.get("/api/auth/config").json() == {"oidc_enabled": False, "local_auth_enabled": True}
    assert client.get("/api/auth/oidc/login").status_code == 404


def test_login_flow_creates_user_session_and_is_idempotent(client: TestClient, sso):
    query, response = start(client, "/projects/abc")
    assert query["code_challenge_method"] == ["S256"] and query["client_id"] == [CLIENT]
    assert "educrea_oidc_flow" in response.headers["set-cookie"] and "samesite=lax" in response.headers["set-cookie"].lower()
    claims_for_next.update({"sub": "u1", "email": "Teacher@Example.org", "email_verified": True, "nonce": query["nonce"][0]})
    done = client.get("/api/auth/oidc/callback", params={"code": "ok", "state": query["state"][0]}, follow_redirects=False)
    assert done.status_code == 303 and done.headers["location"] == "/projects/abc"
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["user"]["email"] == "teacher@example.org"
    user_id = me.json()["user"]["id"]
    client.cookies.clear()
    assert login_as(client).status_code == 303
    assert client.get("/api/auth/me").json()["user"]["id"] == user_id  # same identity -> same account


def test_rejects_bad_state_nonce_audience_reuse_and_missing_cookie(client: TestClient, sso):
    query, _ = start(client)
    claims_for_next.update({"sub": "u1", "email": "a@example.org", "email_verified": True, "nonce": "wrong"})
    assert client.get("/api/auth/oidc/callback", params={"code": "ok", "state": "forged"}).status_code == 400
    query, _ = start(client)
    assert client.get("/api/auth/oidc/callback", params={"code": "ok", "state": query["state"][0]}).status_code == 401  # nonce
    assert client.get("/api/auth/me").status_code == 401
    query, _ = start(client)
    claims_for_next.update({"nonce": query["nonce"][0], "aud": "someone-else"})
    assert client.get("/api/auth/oidc/callback", params={"code": "ok", "state": query["state"][0]}).status_code == 401
    claims_for_next.pop("aud")
    ok_query, _ = start(client)
    claims_for_next["nonce"] = ok_query["nonce"][0]
    assert client.get("/api/auth/oidc/callback", params={"code": "ok", "state": ok_query["state"][0]}, follow_redirects=False).status_code == 303
    assert client.get("/api/auth/oidc/callback", params={"code": "ok", "state": ok_query["state"][0]}).status_code == 400  # one use
    client.cookies.clear()
    assert client.get("/api/auth/oidc/callback", params={"code": "ok", "state": ok_query["state"][0]}).status_code == 400  # other browser
    third, _ = start(client)
    assert client.get("/api/auth/oidc/callback", params={"code": "bad", "state": third["state"][0]}).status_code == 502


def test_next_is_never_an_open_redirect(client: TestClient, sso):
    for hostile in ("//evil.test/x", "https://evil.test", "/\\evil.test", "javascript:alert(1)"):
        query, _ = start(client, hostile)
        claims_for_next.update({"sub": f"s{hostile}", "email": f"{abs(hash(hostile))}@example.org", "email_verified": True,
                                "nonce": query["nonce"][0]})
        done = client.get("/api/auth/oidc/callback", params={"code": "ok", "state": query["state"][0]}, follow_redirects=False)
        assert done.headers["location"] == "/projects"
        client.cookies.clear()


def test_links_existing_local_account_and_cuts_its_password(client: TestClient, sso):
    csrf = register(client, "teacher@example.org")
    project = client.post("/api/projects", headers={"X-CSRF-Token": csrf}, json={"title": "Antes del SSO"}).json()
    client.cookies.clear()
    assert login_as(client, sub="u9", email="teacher@example.org").status_code == 303
    assert [p["title"] for p in client.get("/api/projects").json()] == ["Antes del SSO"]  # nothing lost
    assert project["id"]
    client.cookies.clear()
    bad = client.post("/api/auth/login", json={"email": "teacher@example.org", "password": "a-long-test-password"})
    assert bad.status_code == 401  # pre-registered password no longer works


def test_unverified_email_is_refused_and_local_auth_can_be_disabled(client: TestClient, sso, monkeypatch):
    query, _ = start(client)
    claims_for_next.update({"sub": "u2", "email": "x@example.org", "email_verified": False, "nonce": query["nonce"][0]})
    assert client.get("/api/auth/oidc/callback", params={"code": "ok", "state": query["state"][0]}).status_code == 403
    monkeypatch.setattr(get_settings(), "local_auth_enabled", False)
    assert client.post("/api/auth/register", json={"email": "n@example.org", "password": "a-long-test-password"}).status_code == 403
    assert client.post("/api/auth/login", json={"email": "n@example.org", "password": "a-long-test-password"}).status_code == 403
    assert client.get("/api/auth/config").json()["local_auth_enabled"] is False


def test_rejects_forged_signature_and_expired_token(client: TestClient, sso):
    signing["key"] = ROGUE  # token signed by someone who is not the provider
    query, _ = start(client)
    claims_for_next.update({"sub": "u3", "email": "f@example.org", "email_verified": True, "nonce": query["nonce"][0]})
    assert client.get("/api/auth/oidc/callback", params={"code": "ok", "state": query["state"][0]}).status_code == 401
    signing["key"] = KEY
    query, _ = start(client)
    claims_for_next.update({"nonce": query["nonce"][0], "exp": int(time.time()) - 3600})
    assert client.get("/api/auth/oidc/callback", params={"code": "ok", "state": query["state"][0]}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
