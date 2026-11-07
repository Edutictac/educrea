import asyncio
import base64
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from educrea_api.config import Settings
from educrea_api.main import app
from educrea_api.models import AiUsage, User
from educrea_api.services.ai import images as image_service
from educrea_api.services.ai.providers.base import ProviderError
from educrea_api.services.ai.providers.gemini_image import (
    GeminiImageProvider, GeneratedImage, get_gemini_image_provider)
from test_ai import setup_user
from test_auth_projects import register
from conftest import engine

FIXTURES = Path(__file__).parent / "fixtures"
PNG = (FIXTURES / "trompeta.png").read_bytes()
MODEL = "gemini-3.1-flash-lite-image"
CATALOG = json.dumps({"gemini": {MODEL: {"1K": {"image_microusd": 33600,
                                                "input_microusd_per_million": 250000}}}})


@pytest.fixture
def images(monkeypatch):
    settings = Settings(image_models_json=CATALOG, ai_daily_image_requests=5)
    monkeypatch.setattr(image_service, "get_settings", lambda: settings)
    return settings


class StubImage:
    def __init__(self, data: bytes = PNG, key_seen: list | None = None):
        self.data = data
        self.key_seen = key_seen if key_seen is not None else []

    async def generate(self, api_key, model, prompt, aspect_ratio="1:1", size="1K"):
        self.key_seen.append(api_key)
        return GeneratedImage(self.data, "image/png")


def budget(client: TestClient, headers: dict, micro_usd: int = 1000000):
    assert client.put("/api/ai/budget", headers=headers,
                      json={"monthly_limit_microusd": micro_usd}).status_code == 200


def estimate(client: TestClient, headers: dict, project_id: str, prompt: str = "Una trompeta dorada"):
    response = client.post(f"/api/projects/{project_id}/ai/images/estimate", headers=headers,
                           json={"prompt": prompt, "model": MODEL, "aspect_ratio": "1:1"})
    assert response.status_code == 200, response.text
    return response.json()


def body(est: dict, **extra):
    return {"prompt": "Una trompeta dorada", "model": MODEL, "aspect_ratio": "1:1",
            "paid_authorized": True, "approved_max_cost_microusd": est["maximum_cost_microusd"],
            "approved_estimate_fingerprint": est["fingerprint"],
            "rights_acknowledged": True, "no_personal_data": True, **extra}


def test_catalog_estimate_and_models(client: TestClient, images):
    headers, project_id = setup_user(client)
    data = estimate(client, headers, project_id)
    assert data["image_microusd"] == 33600
    assert data["maximum_cost_microusd"] > data["image_microusd"]
    assert len(data["fingerprint"]) == 64
    status = client.get("/api/ai/images/models")
    assert status.status_code == 200
    payload = status.json()
    assert payload["default"] == MODEL and payload["configured"] is True
    assert payload["models"][0]["prices"] == {"1K": 33600}


def test_generate_preview_accounting_and_save(client: TestClient, images):
    headers, project_id = setup_user(client)
    budget(client, headers)
    est = estimate(client, headers, project_id)
    seen: list[str] = []
    app.dependency_overrides[get_gemini_image_provider] = lambda: StubImage(key_seen=seen)
    response = client.post(f"/api/projects/{project_id}/ai/images", headers=headers, json=body(est))
    assert response.status_code == 200, response.text
    result = response.json()
    raw = base64.b64decode(result["image_base64"])
    assert raw.startswith(b"\x89PNG")
    assert result["cost_microusd"] == est["maximum_cost_microusd"]
    assert result["suggested_credit"].startswith("Generada con IA (Google Gemini")
    assert seen == ["test-only-gemini-key"]
    # Nothing is saved until the teacher accepts the preview.
    assert client.get(f"/api/projects/{project_id}/assets").json() == []
    saved = client.post(f"/api/projects/{project_id}/assets",
                        headers={**headers, "Content-Type": "application/octet-stream"},
                        params={"filename": result["suggested_filename"], "alt": "Una trompeta dorada",
                                "credit": result["suggested_credit"]}, content=raw)
    assert saved.status_code == 201, saved.text
    assert client.get(f"/api/projects/{project_id}/assets").json()[0]["path"].startswith("imagenes/")
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == est["maximum_cost_microusd"]


def test_generation_requires_explicit_confirmation_and_rights(client: TestClient, images):
    headers, project_id = setup_user(client)
    budget(client, headers)
    est = estimate(client, headers, project_id)
    assert client.post(f"/api/projects/{project_id}/ai/images", headers=headers,
                       json={**body(est), "paid_authorized": False}).status_code == 403
    assert client.post(f"/api/projects/{project_id}/ai/images", headers=headers,
                       json={**body(est), "rights_acknowledged": False}).status_code == 422
    assert client.post(f"/api/projects/{project_id}/ai/images", headers=headers,
                       json={**body(est), "approved_max_cost_microusd": 1}).status_code == 403
    assert client.post(f"/api/projects/{project_id}/ai/images", headers=headers,
                       json={**body(est), "no_personal_data": False}).status_code == 422


def test_failed_generation_refunds_budget(client: TestClient, images):
    headers, project_id = setup_user(client)
    budget(client, headers)
    est = estimate(client, headers, project_id)

    class Failing:
        async def generate(self, *args):
            raise ProviderError("sin imagen", 429)

    app.dependency_overrides[get_gemini_image_provider] = lambda: Failing()
    response = client.post(f"/api/projects/{project_id}/ai/images", headers=headers, json=body(est))
    assert response.status_code == 429
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == 0
    with Session(engine) as db:
        row = db.scalar(select(AiUsage))
        assert row.status == "failed" and row.actual_cost_microusd == 0


@pytest.mark.parametrize("failure", ["timeout", "unreadable"])
def test_possibly_billed_failures_keep_counting_against_the_budget(client: TestClient, images, failure):
    headers, project_id = setup_user(client)
    budget(client, headers)
    est = estimate(client, headers, project_id)

    class TimedOut:
        async def generate(self, *args):
            raise ProviderError("tardó demasiado", 504, consumed_unknown=True)

    # «unreadable»: Google delivered (and billed) bytes that are not an image.
    app.dependency_overrides[get_gemini_image_provider] = (
        (lambda: TimedOut()) if failure == "timeout" else (lambda: StubImage(data=b"not an image")))
    response = client.post(f"/api/projects/{project_id}/ai/images", headers=headers, json=body(est))
    assert response.status_code in (502, 504)
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == est["maximum_cost_microusd"]
    with Session(engine) as db:
        row = db.scalar(select(AiUsage))
        assert row.status == "failed" and row.actual_cost_microusd == est["maximum_cost_microusd"]


def test_adapter_marks_unanswered_requests_as_possibly_billed():
    async def run():
        async def slow(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("no answer", request=request)

        async def unreachable(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route", request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as client:
            with pytest.raises(ProviderError) as error:
                await GeminiImageProvider(client).generate("test-key", MODEL, "Una trompeta")
            assert error.value.status_code == 504 and error.value.consumed_unknown
        async with httpx.AsyncClient(transport=httpx.MockTransport(unreachable)) as client:
            with pytest.raises(ProviderError) as error:
                await GeminiImageProvider(client).generate("test-key", MODEL, "Una trompeta")
            assert not error.value.consumed_unknown

    asyncio.run(run())


def test_guest_uses_temporary_key_and_cannot_save_a_key(client: TestClient, images):
    opened = client.post("/api/auth/guest")
    assert opened.status_code == 200
    csrf = opened.json()["csrf_token"]
    project = client.post("/api/projects", headers={"X-CSRF-Token": csrf},
                          json={"title": "Borrador invitado"}).json()["id"]
    budget_headers = {"X-CSRF-Token": csrf}
    budget(client, budget_headers)
    temporary = {"X-Educrea-Temporary-Keys": json.dumps({
        "gemini": {"key": "temporary-gemini-key-123", "confirmed": []}})}
    assert client.put("/api/ai/providers/gemini/key", headers={**temporary, **budget_headers},
                      json={"api_key": "temporary-gemini-key-123"}).status_code == 403
    assert client.get("/api/ai/images/models", headers=temporary).json()["configured"] is True
    est = estimate(client, {**temporary, **budget_headers}, project)
    seen: list[str] = []
    app.dependency_overrides[get_gemini_image_provider] = lambda: StubImage(key_seen=seen)
    response = client.post(f"/api/projects/{project}/ai/images", headers={**temporary, **budget_headers},
                           json=body(est))
    assert response.status_code == 200, response.text
    assert seen == ["temporary-gemini-key-123"]


def test_image_daily_limit_and_no_key(client: TestClient, images):
    images.ai_daily_image_requests = 1
    headers, project_id = setup_user(client)
    budget(client, headers)
    est = estimate(client, headers, project_id)
    app.dependency_overrides[get_gemini_image_provider] = lambda: StubImage()
    assert client.post(f"/api/projects/{project_id}/ai/images", headers=headers, json=body(est)).status_code == 200
    assert client.post(f"/api/projects/{project_id}/ai/images", headers=headers, json=body(est)).status_code == 429

    client.post("/api/auth/logout", headers=headers)
    register(client, "without-key@example.org")
    csrf = client.get("/api/auth/me").json()["csrf_token"]
    project = client.post("/api/projects", headers={"X-CSRF-Token": csrf}, json={"title": "Sin clave"}).json()["id"]
    budget(client, {"X-CSRF-Token": csrf})
    est = estimate(client, {"X-CSRF-Token": csrf}, project)
    assert client.post(f"/api/projects/{project}/ai/images", headers={"X-CSRF-Token": csrf},
                       json=body(est)).status_code == 409


def test_image_adapter_request_and_errors():
    async def run():
        seen = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["key"] = request.headers["x-goog-api-key"]
            seen["revision"] = request.headers["Api-Revision"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"output_image": {
                "data": base64.b64encode(PNG).decode(), "mime_type": "image/png"}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await GeminiImageProvider(client).generate(
                "test-key", MODEL, "Una trompeta", "4:3", "1K")
            assert result.data == PNG and result.media_type == "image/png"
            assert seen["key"] == "test-key" and seen["revision"] == "2026-05-20"
            assert seen["body"]["response_format"]["image_size"] == "1K"
            assert seen["body"]["response_format"]["mime_type"] == "image/jpeg"
            assert seen["body"]["response_format"]["aspect_ratio"] == "4:3"

        async def fail(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "quota"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            with pytest.raises(ProviderError) as error:
                await GeminiImageProvider(client).generate("test-key", MODEL, "Una trompeta")
            assert error.value.status_code == 429

    asyncio.run(run())
