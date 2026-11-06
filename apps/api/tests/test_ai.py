import asyncio
import json

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from edustudio_api.config import Settings
from edustudio_api.models import AiCredential
from edustudio_api.main import app
from edustudio_api.services.ai import engine as ai_engine
from edustudio_api.services.ai import credentials
from edustudio_api.services.ai.providers.base import ProviderChunk, ProviderError, ProviderResult
from edustudio_api.services.ai.providers.gemini import GeminiProvider, get_gemini_provider
from edustudio_api.services.ai.providers.compatible import CompatibleProvider
from edustudio_api.services.ai.providers import registry
from edustudio_api.services.ai import quotas
from edustudio_api.services.ai import pricing
from edustudio_api.services.ai.providers.anthropic import AnthropicProvider
from test_auth_projects import register


class StubGemini:
    def __init__(self, text: str):
        self.text = text

    async def generate(self, _key: str, _model: str, _prompt: str) -> ProviderResult:
        return ProviderResult(self.text, {"input_tokens": 20, "output_tokens": 30})

    async def stream(self, _key: str, _model: str, _prompt: str):
        midpoint = len(self.text) // 2
        yield ProviderChunk(text=self.text[:midpoint])
        yield ProviderChunk(text=self.text[midpoint:], usage={"input_tokens": 20, "output_tokens": 30}, finished=True)


def setup_user(client: TestClient):
    csrf = register(client, "teacher@example.org")
    headers = {"X-CSRF-Token": csrf}
    project = client.post("/api/projects", headers=headers, json={"title": "Fracciones"}).json()
    key_result = client.put("/api/ai/providers/gemini/key", headers=headers,
                            json={"api_key": "test-only-gemini-key"})
    assert key_result.status_code == 204
    assert client.post("/api/ai/providers/gemini/free-models/gemini-test-free/confirm",
                       headers=headers, json={"acknowledged": True}).status_code == 204
    return headers, project["id"]


def test_encrypted_credential_replace_revoke_and_isolation(client: TestClient):
    headers, project_id = setup_user(client)
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from conftest import engine

    with Session(engine) as session:
        stored = session.scalar(select(AiCredential))
        assert stored is not None
        assert "test-only-gemini-key" not in stored.ciphertext
        assert credentials.decrypt_key(stored.ciphertext) == "test-only-gemini-key"
    status = client.get("/api/ai/providers/gemini")
    assert status.json() == {"configured": True, "verified_free_models": ["gemini-test-free"],
                             "confirmed_free_models": ["gemini-test-free"], "paid_models": []}
    assert "test-only-gemini-key" not in status.text
    assert client.put("/api/ai/providers/gemini/key", json={"api_key": "another-test-only-key"}).status_code == 403
    assert client.put("/api/ai/providers/gemini/key", headers=headers,
                      json={"api_key": "another-test-only-key"}).status_code == 204
    assert client.get("/api/ai/providers/gemini").json()["confirmed_free_models"] == []
    assert client.post(f"/api/projects/{project_id}/ai/proposals", headers=headers,
                       json={"instruction": "Crea una actividad de fracciones",
                             "model": "gemini-test-free"}).status_code == 403
    assert client.delete("/api/ai/providers/gemini/key", headers=headers).status_code == 204
    assert client.get("/api/ai/providers/gemini").json()["configured"] is False
    client.post("/api/auth/logout", headers=headers)
    register(client, "other@example.org")
    assert client.get("/api/ai/providers/gemini").json()["configured"] is False


def test_key_rotation_accepts_old_key_without_exposing_it(monkeypatch):
    old, new = Fernet.generate_key(), Fernet.generate_key()
    monkeypatch.setattr(credentials, "get_settings", lambda: Settings(credential_keys=SecretStr(
        new.decode() + "\n" + old.decode())))
    credentials.cipher.cache_clear()
    old_ciphertext = Fernet(old).encrypt(b"example-private-key").decode()
    assert credentials.decrypt_key(old_ciphertext) == "example-private-key"
    rotated = credentials.rotate_ciphertext(old_ciphertext)
    assert Fernet(new).decrypt(rotated.encode()) == b"example-private-key"
    credentials.cipher.cache_clear()


def test_review_apply_restore_and_conflict(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}/files"
    initial = client.post(base, headers=headers, json={"path": "activity.json", "content": "{}"}).json()
    draft = {"summary": "Añade un ejercicio", "changes": [
        {"path": "activity.json", "content": '{"title":"Fracciones"}'},
        {"path": "index.html", "content": "<h1>Fracciones</h1>"},
    ]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(draft))
    route = f"/api/projects/{project_id}/ai/proposals"
    request = {"instruction": "Crea un ejercicio de fracciones", "model": "gemini-test-free",
               "context_paths": ["activity.json"]}
    assert client.post(route, headers=headers, json={**request, "model": "gemini-paid"}).status_code == 403
    proposal_response = client.post(route, headers=headers, json=request)
    assert proposal_response.status_code == 201
    proposal = proposal_response.json()
    assert proposal["status"] == "pending"
    assert proposal["changes"][0]["before_content"] == "{}"
    assert client.get(f"{base}/{initial['id']}").json()["content"] == "{}"
    assert len(client.get(base).json()) == 1
    assert client.post(f"{route}/{proposal['id']}/apply", headers=headers).status_code == 200
    assert client.post(f"{route}/{proposal['id']}/apply", headers=headers).status_code == 409
    assert client.get(f"{base}/{initial['id']}").json()["version"] == 2
    assert sorted(file["path"] for file in client.get(base).json()) == ["activity.json", "index.html"]
    assert client.post(f"{route}/{proposal['id']}/restore", headers=headers).status_code == 200
    assert client.get(f"{base}/{initial['id']}").json()["content"] == "{}"
    assert len(client.get(base).json()) == 1

    second = client.post(route, headers=headers, json=request).json()
    client.put(f"{base}/{initial['id']}", headers=headers,
               json={"content": '{"manual":true}', "expected_version": 3})
    assert client.post(f"{route}/{second['id']}/apply", headers=headers).status_code == 409
    assert client.get(f"{base}/{initial['id']}").json()["content"] == '{"manual":true}'
    assert client.post(f"{route}/{second['id']}/reject", headers=headers).json()["status"] == "rejected"


def test_invalid_proposal_and_other_user_access(client: TestClient):
    headers, project_id = setup_user(client)
    route = f"/api/projects/{project_id}/ai/proposals"
    request = {"instruction": "Crea un ejercicio de fracciones", "model": "gemini-test-free"}
    draft = {"summary": "Malicioso", "changes": [{"path": "../secret.js", "content": "x"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(draft))
    assert client.post(route, headers=headers, json=request).status_code == 422
    assert client.get(route).json() == []
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini("not-json")
    assert client.post(route, headers=headers, json=request).status_code == 502
    assert client.get(route).json() == []
    draft["changes"][0]["path"] = "index.html"
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(draft))
    proposal = client.post(route, headers=headers, json=request).json()
    client.post("/api/auth/logout", headers=headers)
    second_headers = {"X-CSRF-Token": register(client, "other@example.org")}
    assert client.get(route).status_code == 404
    assert client.get(f"{route}/{proposal['id']}").status_code == 404
    assert client.post(f"{route}/{proposal['id']}/apply", headers=second_headers).status_code == 404


def test_unselected_existing_file_cannot_be_changed(client: TestClient):
    headers, project_id = setup_user(client)
    files = f"/api/projects/{project_id}/files"
    client.post(files, headers=headers, json={"path": "activity.json", "content": "{}"})
    original = client.post(files, headers=headers, json={
        "path": "index.html", "content": "<p>Original</p>"}).json()
    draft = {"summary": "Modifica un archivo no compartido", "changes": [
        {"path": "index.html", "content": "<p>Cambiado</p>"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(draft))
    route = f"/api/projects/{project_id}/ai/proposals"
    response = client.post(route, headers=headers, json={
        "instruction": "Crea una actividad sobre fracciones", "model": "gemini-test-free",
        "context_paths": ["activity.json"]})
    assert response.status_code == 422
    assert client.get(route).json() == []
    assert client.get(f"{files}/{original['id']}").json()["content"] == "<p>Original</p>"


def test_streaming_persists_only_complete_proposal(client: TestClient):
    headers, project_id = setup_user(client)
    route = f"/api/projects/{project_id}/ai/proposals"
    request = {"instruction": "Crea un ejercicio de fracciones", "model": "gemini-test-free"}
    draft = {"summary": "Actividad", "changes": [{"path": "index.html", "content": "<p>Hola</p>"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(draft))
    response = client.post(f"{route}/stream", headers=headers, json=request)
    assert response.status_code == 200
    assert "event: token" in response.text
    assert "event: proposal" in response.text
    assert len(client.get(route).json()) == 1


def test_stream_failure_and_unverified_model_do_not_create_proposal(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    route = f"/api/projects/{project_id}/ai/proposals"
    request = {"instruction": "Crea un ejercicio de fracciones", "model": "gemini-test-free"}
    monkeypatch.setattr(ai_engine, "free_models", lambda: [])
    assert client.post(route, headers=headers, json=request).status_code == 503
    monkeypatch.undo()

    class IncompleteGemini(StubGemini):
        async def stream(self, _key, _model, _prompt):
            yield ProviderChunk(text='{"summary":"incompleta"')
            raise ProviderError("Respuesta incompleta de Gemini")

    app.dependency_overrides[get_gemini_provider] = lambda: IncompleteGemini("")
    response = client.post(f"{route}/stream", headers=headers, json=request)
    assert response.status_code == 200
    assert "event: error" in response.text
    assert client.get(route).json() == []


def test_gemini_rest_structured_and_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.headers["x-goog-api-key"] == "test-key"
        body = json.loads(request.content)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": '{"summary":"ok","changes":[]}'}]}}],
            "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 5}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await GeminiProvider(client).generate("test-key", "gemini-test-free", "hello")
            assert result.usage == {"input_tokens": 4, "output_tokens": 5}
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _request: httpx.Response(429))) as client:
            with pytest.raises(ProviderError) as caught:
                await GeminiProvider(client).generate("test-key", "gemini-test-free", "hello")
            assert caught.value.status_code == 429
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, json={"candidates": []}))) as client:
            with pytest.raises(ProviderError):
                await GeminiProvider(client).generate("test-key", "gemini-test-free", "hello")
    asyncio.run(run())


def test_gemini_stream_and_incomplete_response():
    event = json.dumps({"candidates": [{"content": {"parts": [{"text": "abc"}]}, "finishReason": "STOP"}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, text=f"data: {event}\n\n"))) as client:
            chunks = [chunk async for chunk in GeminiProvider(client).stream("test-key", "gemini-test-free", "hello")]
            assert chunks[0].text == "abc"
            assert chunks[0].finished
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, text='data: {"candidates": []}\n\n'))) as client:
            with pytest.raises(ProviderError):
                _chunks = [chunk async for chunk in GeminiProvider(client).stream("test-key", "gemini-test-free", "hello")]
    asyncio.run(run())


def test_additional_providers_require_key_and_confirmation(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    route = f"/api/projects/{project_id}/ai/proposals"
    request = {"instruction": "Crea una actividad de fracciones", "provider": "openrouter", "model": "test/model:free"}
    assert client.post(route, headers=headers, json=request).status_code == 409
    assert client.put("/api/ai/providers/openrouter/key", headers=headers,
                      json={"api_key": "test-openrouter-key"}).status_code == 204
    assert client.post(route, headers=headers, json=request).status_code == 403
    assert client.post("/api/ai/providers/openrouter/free-models/test%2Fmodel:free/confirm",
                       headers=headers, json={"acknowledged": True}).status_code == 204
    assert "test-openrouter-key" not in client.get("/api/ai/providers").text
    draft = {"summary": "Actividad", "changes": [{"path": "index.html", "content": "<h1>Hola</h1>"}]}
    monkeypatch.setattr(registry, "adapter", lambda _name: StubGemini(json.dumps(draft)))
    response = client.post(route, headers=headers, json=request)
    assert response.status_code == 201
    assert response.json()["provider"] == "openrouter"
    quota = client.get("/api/ai/quota").json()
    assert quota["requests_used"] == 1
    assert quota["tokens_used_or_reserved"] == 50
    assert client.delete("/api/ai/providers/openrouter/key", headers=headers).status_code == 204
    assert client.get("/api/ai/providers").json()["openrouter"]["configured"] is False


def test_authorized_fallback_and_quota_limit(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    client.put("/api/ai/providers/groq/key", headers=headers, json={"api_key": "test-groq-secret"})
    client.post("/api/ai/providers/groq/free-models/groq-test-free/confirm",
                headers=headers, json={"acknowledged": True})
    draft = {"summary": "Actividad", "changes": [{"path": "index.html", "content": "<h1>Hola</h1>"}]}

    class RateLimited(StubGemini):
        async def generate(self, *_args):
            raise ProviderError("Cuota alcanzada", 429)

        async def stream(self, *_args):
            raise ProviderError("Cuota alcanzada", 429)
            yield ProviderChunk()

    app.dependency_overrides[get_gemini_provider] = lambda: RateLimited("")
    monkeypatch.setattr(registry, "adapter", lambda _name: StubGemini(json.dumps(draft)))
    route = f"/api/projects/{project_id}/ai/proposals"
    request = {"instruction": "Crea una actividad de fracciones", "model": "gemini-test-free"}
    assert client.post(route, headers=headers, json=request).status_code == 429
    response = client.post(route, headers=headers, json={**request, "allow_fallback": True})
    assert response.status_code == 201
    assert response.json()["provider"] == "groq"
    assert client.get("/api/ai/quota").json()["requests_used"] == 3
    monkeypatch.setattr(quotas, "get_settings", lambda: Settings(ai_daily_personal_requests=3))
    assert client.post(route, headers=headers, json=request).status_code == 429


@pytest.mark.parametrize("status_code", [429, 503, 504])
def test_stream_fallback_only_before_text(client: TestClient, monkeypatch, status_code):
    headers, project_id = setup_user(client)
    client.put("/api/ai/providers/groq/key", headers=headers, json={"api_key": "test-groq-secret"})
    client.post("/api/ai/providers/groq/free-models/groq-test-free/confirm",
                headers=headers, json={"acknowledged": True})
    draft = {"summary": "Actividad", "changes": [{"path": "index.html", "content": "<h1>Hola</h1>"}]}

    class Limited:
        async def stream(self, *_args):
            raise ProviderError("Proveedor no disponible", status_code)
            yield ProviderChunk()

    app.dependency_overrides[get_gemini_provider] = lambda: Limited()
    monkeypatch.setattr(registry, "adapter", lambda _name: StubGemini(json.dumps(draft)))
    route = f"/api/projects/{project_id}/ai/proposals/stream"
    response = client.post(route, headers=headers, json={"instruction": "Crea una actividad de fracciones",
                                                       "model": "gemini-test-free", "allow_fallback": True})
    assert response.status_code == 200
    assert '"provider": "groq"' in response.text
    assert "event: proposal" in response.text

    class Partial:
        async def stream(self, *_args):
            yield ProviderChunk(text="parte")
            raise ProviderError("Cuota alcanzada", 429)

    app.dependency_overrides[get_gemini_provider] = lambda: Partial()
    response = client.post(route, headers=headers, json={"instruction": "Crea una actividad de fracciones",
                                                       "model": "gemini-test-free", "allow_fallback": True})
    assert "event: error" in response.text
    assert response.text.count('"provider": "groq"') == 0


def test_compatible_provider_parses_rest_and_stream():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.groq.com"
        assert request.headers["Authorization"] == "Bearer test-key"
        if request.read().find(b'"stream":true') >= 0:
            event = json.dumps({"choices": [{"delta": {"content": "{}"}, "finish_reason": "stop"}],
                                "usage": {"prompt_tokens": 2, "completion_tokens": 3}})
            return httpx.Response(200, text=f"data: {event}\n\ndata: [DONE]\n\n")
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 2, "completion_tokens": 3}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = CompatibleProvider("groq", client)
            assert (await provider.generate("test-key", "groq-test-free", "hello")).usage == {
                "input_tokens": 2, "output_tokens": 3}
            chunks = [chunk async for chunk in provider.stream("test-key", "groq-test-free", "hello")]
            assert chunks[0].text == "{}"
            assert chunks[0].finished
    asyncio.run(run())


@pytest.mark.parametrize("status_code", [503, 504])
def test_compatible_provider_preserves_saturation_status(status_code):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _request: httpx.Response(status_code))) as client:
            provider = CompatibleProvider("mistral", client)
            with pytest.raises(ProviderError) as error:
                await provider.generate("test-key", "mistral-small-latest", "JSON")
            assert error.value.status_code == status_code
    asyncio.run(run())


def test_administered_ollama_needs_no_personal_key(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    monkeypatch.setattr(registry, "get_settings", lambda: Settings(
        ollama_base_url="http://127.0.0.1:11434", ollama_free_models="llama-test"))
    assert client.get("/api/ai/providers").json()["ollama"]["confirmed_free_models"] == ["llama-test"]
    draft = {"summary": "Actividad", "changes": [{"path": "index.html", "content": "<h1>Hola</h1>"}]}
    monkeypatch.setattr(registry, "adapter", lambda _name: StubGemini(json.dumps(draft)))
    route = f"/api/projects/{project_id}/ai/proposals"
    response = client.post(route, headers=headers, json={"instruction": "Crea una actividad de fracciones",
                                                       "provider": "ollama", "model": "llama-test"})
    assert response.status_code == 201
    assert response.json()["provider"] == "ollama"
    assert client.post(route, headers=headers, json={"instruction": "Crea una actividad de fracciones",
                                                  "provider": "ollama", "model": "unlisted-paid"}).status_code == 403


def test_ollama_adapter_uses_managed_url_and_json_format():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        assert "Authorization" not in request.headers
        assert json.loads(request.content)["format"] == "json"
        return httpx.Response(200, json={"message": {"content": '{"summary":"ok"}'},
                                         "done": True, "prompt_eval_count": 4, "eval_count": 6})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await CompatibleProvider("ollama", client, "http://127.0.0.1:11434").generate(
                "", "llama-test", "hello")
            assert result.usage == {"input_tokens": 4, "output_tokens": 6}
    asyncio.run(run())


def test_paid_estimate_budget_authorization_and_accounting(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    monkeypatch.setattr(pricing, "get_settings", lambda: Settings(paid_models_json=json.dumps({
        "openai": {"openai-test": {"input": 500000, "output": 2000000}}})))
    assert client.get("/api/ai/providers").json()["openai"]["paid_models"][0]["model"] == "openai-test"
    assert client.put("/api/ai/providers/openai/key", headers=headers,
                      json={"api_key": "test-openai-personal-key"}).status_code == 204
    assert "test-openai-personal-key" not in client.get("/api/ai/providers").text
    draft = {"summary": "Actividad", "changes": [{"path": "index.html", "content": "<h1>Hola</h1>"}]}
    monkeypatch.setattr(registry, "adapter", lambda _name: StubGemini(json.dumps(draft)))
    request = {"instruction": "Crea una actividad de fracciones", "provider": "openai",
               "model": "openai-test", "mode": "paid"}
    estimate_route = f"/api/projects/{project_id}/ai/estimate"
    estimate = client.post(estimate_route, headers=headers, json=request)
    assert estimate.status_code == 200
    maximum = estimate.json()["maximum_cost_microusd"]
    assert maximum > 0
    route = f"/api/projects/{project_id}/ai/proposals"
    assert client.post(route, headers=headers, json={**request, "model": "not-priced"}).status_code == 403
    assert client.post(route, headers=headers, json=request).status_code == 403
    approved = {**request, "paid_authorized": True, "approved_max_cost_microusd": maximum,
                "approved_estimate_fingerprint": estimate.json()["fingerprint"]}
    assert client.post(route, headers=headers, json=approved).status_code == 429
    assert client.put("/api/ai/budget", json={"monthly_limit_microusd": 1000000}).status_code == 403
    assert client.put("/api/ai/budget", headers=headers,
                      json={"monthly_limit_microusd": 20000001}).status_code == 422
    assert client.put("/api/ai/budget", headers=headers,
                      json={"monthly_limit_microusd": maximum - 1}).status_code == 200
    assert client.post(route, headers=headers, json=approved).status_code == 429
    assert client.put("/api/ai/budget", headers=headers,
                      json={"monthly_limit_microusd": 1000000}).status_code == 200
    assert client.post(route, headers=headers, json={**approved,
        "approved_max_cost_microusd": maximum - 1}).status_code == 403
    assert client.post(route, headers=headers, json={**approved,
        "instruction": "Crea una actividad de fraccionez"}).status_code == 403
    response = client.post(route, headers=headers, json=approved)
    assert response.status_code == 201
    assert response.json()["provider"] == "openai"
    expected = pricing.cost(20, 30, pricing.Price(500000, 2000000))
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == expected
    client.post("/api/auth/logout", headers=headers)
    register(client, "other-paid@example.org")
    assert client.get("/api/ai/budget").json()["monthly_limit_microusd"] == 0
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == 0


def test_anthropic_adapter_and_paid_error_do_not_reveal_key():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.anthropic.com"
        assert request.headers["x-api-key"] == "test-private-key"
        assert request.headers["anthropic-version"]
        return httpx.Response(200, json={"stop_reason": "end_turn", "content": [
            {"type": "text", "text": '{"summary":"ok"}'}],
            "usage": {"input_tokens": 4, "output_tokens": 6}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await AnthropicProvider(client).generate("test-private-key", "claude-test", "hello")
            assert result.usage == {"input_tokens": 4, "output_tokens": 6}
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _request: httpx.Response(401, json={"error": "test-private-key"}))) as client:
            with pytest.raises(ProviderError) as caught:
                await AnthropicProvider(client).generate("test-private-key", "claude-test", "hello")
            assert "test-private-key" not in str(caught.value)
    asyncio.run(run())


def test_paid_stream_requires_approval_and_never_falls_back(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    monkeypatch.setattr(pricing, "get_settings", lambda: Settings(paid_models_json=json.dumps({
        "anthropic": {"claude-test": {"input": 1000000, "output": 3000000}}})))
    client.put("/api/ai/providers/anthropic/key", headers=headers,
               json={"api_key": "test-anthropic-key"})
    client.put("/api/ai/budget", headers=headers, json={"monthly_limit_microusd": 1000000})
    request = {"instruction": "Crea una actividad de fracciones", "provider": "anthropic",
               "model": "claude-test", "mode": "paid", "allow_fallback": True}
    estimate = client.post(f"/api/projects/{project_id}/ai/estimate", headers=headers, json=request).json()
    route = f"/api/projects/{project_id}/ai/proposals/stream"
    assert client.post(route, headers=headers, json=request).status_code == 403

    class Limited(StubGemini):
        async def stream(self, *_args):
            raise ProviderError("Cuota Anthropic alcanzada", 429)
            yield ProviderChunk()

    monkeypatch.setattr(registry, "adapter", lambda _name: Limited(""))
    approved = {**request, "paid_authorized": True,
                "approved_max_cost_microusd": estimate["maximum_cost_microusd"],
                "approved_estimate_fingerprint": estimate["fingerprint"]}
    response = client.post(route, headers=headers, json=approved)
    assert response.status_code == 200
    assert "event: error" in response.text
    assert '"provider": "gemini"' not in response.text
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == estimate[
        "maximum_cost_microusd"]


def test_anthropic_stream_parses_tokens_and_usage():
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 4}}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "{}"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
         "usage": {"output_tokens": 6}},
    ]
    body = "".join(f"data: {json.dumps(event)}\n\n" for event in events)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, text=body))) as client:
            chunks = [chunk async for chunk in AnthropicProvider(client).stream(
                "test-key", "claude-test", "hello")]
            assert chunks[0].text == "{}"
            assert chunks[-1].usage == {"input_tokens": 4, "output_tokens": 6}
            assert chunks[-1].finished
    asyncio.run(run())



def test_limits_apply_by_resource_not_globally(client: TestClient, monkeypatch):
    """Personal-key providers ignore the shared-server limits; Ollama is capped; one generation at a time."""
    from datetime import datetime, timezone

    from conftest import engine as test_engine
    from edustudio_api.models import AiUsage, User
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    setup_user(client)
    done = {"input_tokens": 1, "output_tokens": 1}
    with Session(test_engine) as db:
        user_id = db.scalar(select(User.id))
        other = User(email="other@example.org", password_hash="x")
        db.add(other)
        db.commit()
        for _ in range(250):  # a crowd on a personal provider must not block anyone
            db.add(AiUsage(user_id=other.id, provider="gemini", model="m", reserved_tokens=16384,
                           actual_tokens=16384, status="completed", created_at=datetime.now(timezone.utc)))
        db.commit()
        monkeypatch.setattr(quotas, "get_settings",
                            lambda: Settings(ai_daily_user_requests=2, ai_daily_installation_requests=3))
        quotas.reconcile(db, quotas.reserve(db, user_id, "gemini", "gemini-test-free"), done)
        first = quotas.reserve(db, user_id, "ollama", "qwen")
        with pytest.raises(HTTPException) as busy:
            quotas.reserve(db, user_id, "ollama", "qwen")
        assert "en curso" in busy.value.detail
        quotas.reconcile(db, first, done)
        quotas.reconcile(db, quotas.reserve(db, user_id, "ollama", "qwen"), done)
        with pytest.raises(HTTPException) as per_user:
            quotas.reserve(db, user_id, "ollama", "qwen")
        assert per_user.value.status_code == 429 and "compartido" in per_user.value.detail
        quotas.reconcile(db, quotas.reserve(db, other.id, "ollama", "qwen"), done)  # 3rd shared request overall
        with pytest.raises(HTTPException) as per_installation:
            quotas.reserve(db, other.id, "ollama", "qwen")
        assert "compartido" in per_installation.value.detail
        quotas.reconcile(db, quotas.reserve(db, user_id, "groq", "g"), done)  # personal still fine
        monkeypatch.setattr(quotas, "get_settings", lambda: Settings(ai_daily_personal_requests=1))
        with pytest.raises(HTTPException) as guard:
            quotas.reserve(db, user_id, "groq", "g")
        assert guard.value.status_code == 429 and "seguridad" in guard.value.detail


def test_automatic_context_picks_files_within_budget(client: TestClient):
    from edustudio_api.models import ProjectFile
    from edustudio_api.services.ai import engine as e
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    def file(path, size, age=0):
        return ProjectFile(path=path, content="x" * size, version=1, updated_at=now - timedelta(minutes=age))

    small = [file("index.html", 1000), file("style.css", 1000, 5), file("script.js", 1000, 1)]
    chosen, skipped = e.automatic_context(small, "Mejora la actividad")
    assert chosen == {"index.html", "style.css", "script.js"} and skipped == []
    big = [file("index.html", 30000), file("notas.md", 30000, 9), file("huge.js", 60000, 1), file("a.css", 5000, 2)]
    chosen, skipped = e.automatic_context(big, "Cambia los colores de a.css")
    assert "a.css" in chosen and "index.html" in chosen   # named in the instruction, and the entry point
    assert "huge.js" in skipped and len(json.dumps(sorted(chosen))) < e.MAX_CONTEXT_BYTES


def test_automatic_mode_needs_no_selection_and_never_exceeds_context(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}/files"
    for index in range(8):
        assert client.post(base, headers=headers, json={"path": f"datos{index}.json", "content": '{"v":"' + "é" * 40000 + '"}'}).status_code == 201
    client.put("/api/ai/providers/groq/key", headers=headers, json={"api_key": "test-groq-secret"})
    client.post("/api/ai/providers/groq/free-models/groq-test-free/confirm", headers=headers, json={"acknowledged": True})
    draft = {"summary": "Cambio", "changes": [{"path": "nuevo.html", "content": "<p>Hola</p>"}]}
    captured = {}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)

    monkeypatch.setattr(registry, "adapter", lambda _name: Capture(json.dumps(draft)))
    request = {"instruction": "Crea una página nueva sobre las notas", "provider": "groq", "model": "groq-test-free",
               "automatic": True}
    response = client.post(f"/api/projects/{project_id}/ai/proposals", headers=headers, json=request)
    assert response.status_code == 201, response.text
    assert "not_included_paths" in captured["prompt"] and "Decide tú qué archivos" in captured["prompt"]
    manual = client.post(f"/api/projects/{project_id}/ai/proposals", headers=headers, json={**request, "automatic": False})
    assert manual.status_code == 201  # manual mode with an empty selection is still allowed


def test_gemini_overload_and_timeout_give_actionable_errors():
    for status, expected in ((503, 503), (403, 502), (404, 502)):
        with pytest.raises(ProviderError) as caught:
            GeminiProvider.check_response(httpx.Response(status))
        assert caught.value.status_code == expected

    def slow(_request):
        raise httpx.ReadTimeout("slow")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as client:
            await GeminiProvider(client).generate("key", "gemini-test-free", "hola")
    with pytest.raises(ProviderError) as caught:
        asyncio.run(run())
    assert caught.value.status_code == 504 and "tardó" in str(caught.value)


def test_auto_apply_applies_once_and_can_be_undone(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    client.put("/api/ai/providers/groq/key", headers=headers, json={"api_key": "test-groq-secret"})
    client.post("/api/ai/providers/groq/free-models/groq-test-free/confirm", headers=headers, json={"acknowledged": True})
    draft = {"summary": "Portada", "changes": [{"path": "index.html", "content": "<h1>Música</h1>"}]}
    monkeypatch.setattr(registry, "adapter", lambda _name: StubGemini(json.dumps(draft)))
    route = f"/api/projects/{project_id}/ai/proposals"
    request = {"instruction": "Crea una portada de música", "provider": "groq", "model": "groq-test-free", "automatic": True}
    pending = client.post(route, headers=headers, json=request).json()
    assert pending["status"] == "pending"  # without auto_apply nothing changes
    assert client.get(f"/api/projects/{project_id}/files").json() == []
    client.post(f"{route}/{pending['id']}/reject", headers=headers)
    applied = client.post(route, headers=headers, json={**request, "auto_apply": True})
    assert applied.status_code == 201 and applied.json()["status"] == "applied"
    index = next(f for f in client.get(f"/api/projects/{project_id}/files").json() if f["path"] == "index.html")
    assert client.get(f"/api/projects/{project_id}/files/{index['id']}").json()["content"] == "<h1>Música</h1>"
    undone = client.post(f"{route}/{applied.json()['id']}/restore", headers=headers)
    assert undone.status_code == 200 and undone.json()["status"] == "restored"
    assert "index.html" not in {f["path"] for f in client.get(f"/api/projects/{project_id}/files").json()}


def test_auto_apply_also_in_streaming(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    client.put("/api/ai/providers/groq/key", headers=headers, json={"api_key": "test-groq-secret"})
    client.post("/api/ai/providers/groq/free-models/groq-test-free/confirm", headers=headers, json={"acknowledged": True})
    draft = {"summary": "Portada", "changes": [{"path": "index.html", "content": "<h1>Música</h1>"}]}
    monkeypatch.setattr(registry, "adapter", lambda _name: StubGemini(json.dumps(draft)))
    request = {"instruction": "Crea una portada de música", "provider": "groq", "model": "groq-test-free",
               "automatic": True, "auto_apply": True}
    response = client.post(f"/api/projects/{project_id}/ai/proposals/stream", headers=headers, json=request)
    assert response.status_code == 200 and '"status": "applied"' in response.text
    assert [f["path"] for f in client.get(f"/api/projects/{project_id}/files").json()] == ["index.html"]


def test_prompt_treats_activity_json_as_the_teacher_brief(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    client.post(f"/api/projects/{project_id}/files", headers=headers, json={"path": "activity.json", "content": '{"level":"infantil"}'})
    client.put("/api/ai/providers/groq/key", headers=headers, json={"api_key": "test-groq-secret"})
    client.post("/api/ai/providers/groq/free-models/groq-test-free/confirm", headers=headers, json={"acknowledged": True})
    captured = {}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)

    draft = {"summary": "x", "changes": [{"path": "index.html", "content": "<p>x</p>"}]}
    monkeypatch.setattr(registry, "adapter", lambda _name: Capture(json.dumps(draft)))
    response = client.post(f"/api/projects/{project_id}/ai/proposals", headers=headers, json={
        "instruction": "Crea la actividad", "provider": "groq", "model": "groq-test-free", "automatic": True})
    assert response.status_code == 201
    prompt = captured["prompt"]
    assert "activity.json" in prompt and "encargo del docente" in prompt and "alto contraste" in prompt
    assert "infantil" in prompt and "activity.json" in prompt  # the brief itself reaches the model as context


def test_first_version_from_brief(client: TestClient, monkeypatch):
    route = None
    # 1) A teacher with a brief but no configured provider gets a clear 409 (not a provider call).
    csrf = register(client, "nobrief@example.org")
    headers2 = {"X-CSRF-Token": csrf}
    other = client.post("/api/projects", headers=headers2, json={"title": "Sin proveedor"}).json()
    client.post(f"/api/projects/{other['id']}/files", headers=headers2,
                json={"path": "activity.json", "content": '{"title":"X"}'})
    assert client.post(f"/api/projects/{other['id']}/ai/from-brief", headers=headers2).status_code == 409
    client.post("/api/auth/logout", headers=headers2)

    # 2) Missing brief.
    headers, project_id = setup_user(client)
    route = f"/api/projects/{project_id}/ai/from-brief"
    assert client.post(route, headers=headers).status_code == 409
    brief = {"title": "Els instruments", "activity_type": "juego", "language": "va", "level": "infantil",
             "instructions": "Relaciona cada instrumento con su sonido.",
             "accessibility": {"large_text": True, "high_contrast": True}}
    client.post(f"/api/projects/{project_id}/files", headers=headers, json={"path": "activity.json", "content": json.dumps(brief)})
    captured = {}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)

    draft = {"summary": "Primera versión", "changes": [
        {"path": "index.html", "content": '<html lang="ca"><h1>Els instruments</h1></html>'},
        {"path": "style.css", "content": "body{font-size:1.4rem}"},
        {"path": "script.js", "content": "const a = 1;"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: Capture(json.dumps(draft))
    response = client.post(route, headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "applied" and response.json()["provider"] == "gemini"
    assert [f["path"] for f in client.get(f"/api/projects/{project_id}/files").json()] == [
        "activity.json", "index.html", "script.js", "style.css"]
    prompt = captured["prompt"]
    for expected in ("valenciano", 'lang="ca"', "Educación Infantil", "juego", "Relaciona cada instrumento",
                     "texto grande y alto contraste", "Els instruments"):
        assert expected in prompt, expected
    assert "primera versión" in response.json()["summary"].lower()
    brief_file = next(f for f in client.get(f"/api/projects/{project_id}/files").json() if f["path"] == "activity.json")
    assert json.loads(client.get(f"/api/projects/{project_id}/files/{brief_file['id']}").json()["content"])["level"] == "infantil"


SITUATION_MD = "\n\n".join(f"## {section}\n\nContenido de {section}." for section in (
    "Datos de la situación", "Contexto y justificación", "Reto y producto final",
    "Competencias específicas y criterios de evaluación", "Saberes básicos", "Secuencia de sesiones",
    "Evaluación", "Atención a la diversidad (DUA)", "Materiales y recursos"))


def test_situation_from_brief_generates_markdown_and_requires_all_sections(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    brief = {"kind": "situacion", "title": "L'hort escolar", "language": "va", "level": "primaria", "course": "4t",
             "area": "Coneixement del medi", "sessions": 6, "challenge": "Com podem cuidar l'hort?", "final_product": "Guia",
             "accessibility": {"large_text": False, "high_contrast": False}}
    client.post(f"/api/projects/{project_id}/files", headers=headers, json={"path": "activity.json", "content": json.dumps(brief)})
    captured = {}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)

    good = {"summary": "Situació", "changes": [{"path": "situacion.md", "content": SITUATION_MD}]}
    app.dependency_overrides[get_gemini_provider] = lambda: Capture(json.dumps(good))
    route = f"/api/projects/{project_id}/ai/from-brief"
    response = client.post(route, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "applied" and body["grounding"]["sections_missing"] == []
    assert body["grounding"]["kind"] == "situacion" and body["grounding"]["supported"] is True
    md = next(f for f in client.get(f"/api/projects/{project_id}/files").json() if f["path"] == "situacion.md")
    assert "## Atención a la diversidad (DUA)" in client.get(f"/api/projects/{project_id}/files/{md['id']}").json()["content"]
    prompt = captured["prompt"]
    for expected in ("SITUACIÓN DE APRENDIZAJE", "situacion.md", "## Seqüència de sessions", "valenciano",
                     "Curso o ciclo: 4t", "L'hort escolar", "6", "Guia" if False else "Guia"):
        assert expected in prompt, expected

    # A model that skips a section must not be applied automatically.
    partial = {"summary": "Incompleta", "changes": [{"path": "situacion.md", "content": SITUATION_MD.split("## Evaluación")[0]}]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(partial))
    pending = client.post(route, headers=headers).json()
    assert pending["status"] == "pending" and "Evaluación" in pending["grounding"]["sections_missing"]
    content = client.get(f"/api/projects/{project_id}/files/{md['id']}").json()["content"]
    assert "## Evaluación" in content  # previous good version untouched


def test_section_check_accepts_translated_heading_variants():
    from edustudio_api.services.ai import engine as e

    valencian = """## Dades de la situació
## Context i justificació
## Repte i producte final
## Competències específiques i criteris d'avaluació
## Sabers bàsics del área
## Seqüència de sessions
## Avaluació
## Atenció a la diversitat (DUA)
## Materials i recursos"""
    assert e.missing_sections(valencian) == []
    assert e.missing_sections("### Saberes básicos\n") == [s for s in e.SITUATION_SECTIONS if s != "Saberes básicos"]
    assert "Saberes básicos" in e.missing_sections("## Evaluación\n")


def test_dua_adaptation_reports_barriers_and_requires_all_three_principles(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    original = '<html lang="es"><h1>Fracciones</h1><p>Responde.</p></html>'
    client.post(f"{base}/files", headers=headers, json={"path": "index.html", "content": original})
    route = f"{base}/ai/dua"
    assert client.post(route, headers=headers, json={"path": "style.css"}).status_code == 422
    assert client.post(route, headers=headers, json={"path": "otro.html"}).status_code == 404
    captured = {}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)

    measures = [{"principle": p, "barrier": "b", "measure": "m"}
                for p in ("representacion", "accion_expresion", "implicacion")]
    adapted = '<html lang="es"><h1>Fracciones</h1><p>Elige cómo responder.</p></html>'
    good = {"summary": "Adaptación DUA", "changes": [{"path": "index.html", "content": adapted}],
            "dua": {"barriers": ["Solo texto"], "measures": measures}}
    app.dependency_overrides[get_gemini_provider] = lambda: Capture(json.dumps(good))
    body = client.post(route, headers=headers, json={"path": "index.html", "needs": "Dos alumnos con baja visión",
                                                     "auto_apply": True}).json()
    assert body["status"] == "applied" and body["grounding"]["kind"] == "dua"
    assert body["grounding"]["principles_missing"] == [] and body["grounding"]["barriers"] == ["Solo texto"]
    for expected in ("ADAPTACIÓN DUA", "index.html", "representación", "implicación", "baja visión"):
        assert expected in captured["prompt"], expected
    assert client.post(f"{base}/ai/proposals/{body['id']}/restore", headers=headers).json()["status"] == "restored"

    # Missing a principle: never applied automatically.
    partial = {**good, "dua": {"barriers": [], "measures": measures[:2]}}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(partial))
    pending = client.post(route, headers=headers, json={"path": "index.html", "auto_apply": True}).json()
    assert pending["status"] == "pending" and pending["grounding"]["principles_missing"] == ["Implicación (el porqué)"]
    # Advanced mode (no auto_apply) always waits for review.
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(good))
    assert client.post(route, headers=headers, json={"path": "index.html"}).json()["status"] == "pending"
    index = next(f for f in client.get(f"{base}/files").json() if f["path"] == "index.html")
    assert client.get(f"{base}/files/{index['id']}").json()["content"] == original


def test_first_version_falls_back_to_openrouter_when_gemini_is_saturated(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    client.put("/api/ai/providers/openrouter/key", headers=headers, json={"api_key": "test-only-openrouter-key"})
    assert client.post("/api/ai/providers/openrouter/free-models/test/model:free/confirm", headers=headers,
                       json={"acknowledged": True}).status_code == 204
    client.post(f"/api/projects/{project_id}/files", headers=headers,
                json={"path": "activity.json", "content": json.dumps({"title": "Volcanes", "instructions": "Una página"})})

    class Saturated:
        async def generate(self, *_args):
            raise ProviderError("Gemini está saturado", 503)

    used = []
    draft = {"summary": "Hecho", "changes": [{"path": "index.html", "content": "<h1>Volcanes</h1>"}]}

    def adapter(name):
        used.append(name)
        return StubGemini(json.dumps(draft))

    app.dependency_overrides[get_gemini_provider] = lambda: Saturated()
    monkeypatch.setattr(registry, "adapter", adapter)
    body = client.post(f"/api/projects/{project_id}/ai/from-brief", headers=headers).json()
    assert body["provider"] == "openrouter" and body["status"] == "applied" and used == ["openrouter"]
    # Without another free provider the error is reported as before.
    client.delete("/api/ai/providers/openrouter/key", headers=headers)
    assert client.post(f"/api/projects/{project_id}/ai/from-brief", headers=headers).status_code == 503


def test_first_version_uses_the_ai_chosen_in_the_selector(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    client.put("/api/ai/providers/openrouter/key", headers=headers, json={"api_key": "test-only-openrouter-key"})
    client.post("/api/ai/providers/openrouter/free-models/test/model:free/confirm", headers=headers, json={"acknowledged": True})
    client.post(f"/api/projects/{project_id}/files", headers=headers,
                json={"path": "activity.json", "content": json.dumps({"title": "Volcanes", "instructions": "Una página"})})
    draft = {"summary": "Hecho", "changes": [{"path": "index.html", "content": "<h1>Volcanes</h1>"}]}
    used = []
    monkeypatch.setattr(registry, "adapter", lambda name: used.append(name) or StubGemini(json.dumps(draft)))
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(draft))
    route = f"/api/projects/{project_id}/ai/from-brief"
    body = client.post(route, headers=headers, json={"provider": "openrouter", "model": "test/model:free"}).json()
    assert body["provider"] == "openrouter" and used == ["openrouter"]
    assert client.post(route, headers=headers, json={}).json()["provider"] == "gemini"  # «Automática»
    assert client.post(route, headers=headers).json()["provider"] == "gemini"  # old clients without body
    assert client.post(route, headers=headers, json={"provider": "openrouter", "model": "otro"}).status_code == 403
    assert client.post(route, headers=headers, json={"provider": "mistral", "model": "mistral-small-latest"}).status_code == 422
    assert client.post(route, headers=headers, json={"provider": "openai", "model": "gpt-x"}).status_code == 422


def test_mistral_requires_paid_mode_and_verified_prices(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    client.put("/api/ai/providers/mistral/key", headers=headers, json={"api_key": "test-only-mistral-key"})
    status = client.get("/api/ai/providers/mistral").json()
    assert status["verified_free_models"] == status["confirmed_free_models"] == []
    assert client.post("/api/ai/providers/mistral/free-models/mistral-small-latest/confirm", headers=headers,
                       json={"acknowledged": True}).status_code == 403
    monkeypatch.setattr(pricing, "get_settings", lambda: Settings(paid_models_json=json.dumps({
        "mistral": {"mistral-small-latest": {"input": 100000, "output": 300000}}})))
    assert client.get("/api/ai/providers/mistral").json()["paid_models"][0]["model"] == "mistral-small-latest"
    estimate = client.post(f"/api/projects/{project_id}/ai/estimate", headers=headers, json={
        "instruction": "Crea una actividad de fracciones", "provider": "mistral",
        "model": "mistral-small-latest", "mode": "paid"})
    assert estimate.status_code == 200


def test_draft_changes_ignore_extra_fields_copied_from_the_context():
    draft = ai_engine.parse_draft(json.dumps({
        "summary": "Hecho",
        "changes": [{"path": "situacion.md", "content": "# Título", "version": 4}],
    }))
    assert draft.changes[0].path == "situacion.md"
    assert draft.changes[0].content == "# Título"


def test_invalid_draft_error_names_the_provider():
    with pytest.raises(HTTPException) as error:
        ai_engine.parse_draft('{"summary": "cortado"', "groq")
    assert error.value.status_code == 502
    assert "Groq" in str(error.value.detail)


def test_draft_tolerates_citations_inside_a_change_and_string_not_covered():
    draft = ai_engine.parse_draft(json.dumps({
        "summary": "Hecho",
        "changes": [{"path": "situacion.md", "content": "# Título", "version": 2,
                     "citations": [{"chunk": "F1", "quote": "una cita", "used_for": "justificación"}]}],
        "not_covered": "F2 i F3 no són rellevants",
        "extra": True,
    }))
    assert draft.not_covered == ["F2 i F3 no són rellevants"]
    assert [citation.quote for citation in draft.citations] == ["una cita"]


def test_parse_draft_accepts_fences_prose_and_trailing_commas():
    text = ('Aquí tienes la propuesta:\n```json\n'
            '{"summary": "Hecho", "changes": [{"path": "index.html", "content": "<p>x</p>"},]}\n'
            '```\n')
    draft = ai_engine.parse_draft(text)
    assert draft.summary == "Hecho"
    assert draft.changes[0].path == "index.html"


def test_invalid_proposal_falls_back_to_the_next_free_provider(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    for name, model in (("groq", "groq-test-free"), ("openrouter", "test/model:free")):
        client.put(f"/api/ai/providers/{name}/key", headers=headers, json={"api_key": f"test-{name}-key"})
        assert client.post(f"/api/ai/providers/{name}/free-models/{model}/confirm", headers=headers,
                           json={"acknowledged": True}).status_code == 204
    client.post(f"/api/projects/{project_id}/files", headers=headers,
                json={"path": "index.html", "content": "<p>antes</p>"})
    draft = {"summary": "Hecho", "changes": [{"path": "index.html", "content": "<h1>Después</h1>"}]}

    class Bad:
        async def generate(self, *_args):
            return ProviderResult("esto no es JSON", {})

    class Good:
        async def generate(self, *_args):
            return ProviderResult(json.dumps(draft), {})

    used = []

    def adapter(name):
        used.append(name)
        return Bad() if name == "groq" else Good()

    monkeypatch.setattr(registry, "adapter", adapter)
    app.dependency_overrides[get_gemini_provider] = lambda: Bad()
    response = client.post(f"/api/projects/{project_id}/ai/proposals", headers=headers,
                           json={"instruction": "Crea una portada", "provider": "groq", "model": "groq-test-free",
                                 "context_paths": ["index.html"], "allow_fallback": True})
    body = response.json()
    assert body.get("provider") == "openrouter", (response.status_code, body)
    assert used[0] == "groq" and used[-1] == "openrouter"


def test_truncated_response_tries_another_model_of_the_same_provider(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    original = registry.free_models
    monkeypatch.setattr(registry, "free_models", lambda provider: (
        ["test/model:free", "test/model-2:free"] if provider == "openrouter" else original(provider)))
    client.put("/api/ai/providers/openrouter/key", headers=headers, json={"api_key": "test-openrouter-key"})
    for name in ("test/model:free", "test/model-2:free"):
        assert client.post(f"/api/ai/providers/openrouter/free-models/{name}/confirm", headers=headers,
                           json={"acknowledged": True}).status_code == 204
    client.post(f"/api/projects/{project_id}/files", headers=headers,
                json={"path": "index.html", "content": "<p>antes</p>"})
    draft = {"summary": "Hecho", "changes": [{"path": "index.html", "content": "<h1>Después</h1>"}]}
    models = []

    class TruncatedThenGood:
        async def generate(self, _key, model, _prompt):
            models.append(model)
            if model == "test/model:free":
                raise ProviderError("OpenRouter cortó la respuesta", 502, truncated=True)
            return ProviderResult(json.dumps(draft), {})

    monkeypatch.setattr(registry, "adapter", lambda _name: TruncatedThenGood())
    body = client.post(f"/api/projects/{project_id}/ai/proposals", headers=headers,
                       json={"instruction": "Crea una portada", "provider": "openrouter", "model": "test/model:free",
                             "context_paths": ["index.html"], "allow_fallback": True}).json()
    assert body["provider"] == "openrouter" and body["model"] == "test/model-2:free"
    assert models == ["test/model:free", "test/model-2:free"]


def test_stream_truncated_response_switches_even_after_text(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    client.put("/api/ai/providers/groq/key", headers=headers, json={"api_key": "test-groq-secret"})
    client.post("/api/ai/providers/groq/free-models/groq-test-free/confirm",
                headers=headers, json={"acknowledged": True})
    draft = {"summary": "Actividad", "changes": [{"path": "index.html", "content": "<h1>Hola</h1>"}]}

    class Truncated:
        async def stream(self, *_args):
            yield ProviderChunk(text="parte")
            raise ProviderError("Gemini cortó la respuesta", 502, truncated=True)

    app.dependency_overrides[get_gemini_provider] = lambda: Truncated()
    monkeypatch.setattr(registry, "adapter", lambda _name: StubGemini(json.dumps(draft)))
    response = client.post(f"/api/projects/{project_id}/ai/proposals/stream", headers=headers,
                           json={"instruction": "Crea una actividad de fracciones", "model": "gemini-test-free",
                                 "allow_fallback": True})
    assert '"provider": "groq"' in response.text
    assert "event: proposal" in response.text


def test_stream_error_reports_code_and_provider(client: TestClient):
    headers, project_id = setup_user(client)

    class Truncated:
        async def stream(self, *_args):
            yield ProviderChunk(text="parte")
            raise ProviderError("Gemini cortó la respuesta", 502, truncated=True)

    app.dependency_overrides[get_gemini_provider] = lambda: Truncated()
    response = client.post(f"/api/projects/{project_id}/ai/proposals/stream", headers=headers,
                           json={"instruction": "Crea una actividad de fracciones", "model": "gemini-test-free"})
    assert '"code": "provider_truncated"' in response.text
    assert '"provider": "gemini"' in response.text
