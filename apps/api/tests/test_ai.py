import asyncio
import json

import httpx
import pytest
from cryptography.fernet import Fernet
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
    monkeypatch.setattr(quotas, "get_settings", lambda: Settings(ai_daily_user_requests=3))
    assert client.post(route, headers=headers, json=request).status_code == 429


def test_stream_fallback_only_before_text(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)
    client.put("/api/ai/providers/groq/key", headers=headers, json={"api_key": "test-groq-secret"})
    client.post("/api/ai/providers/groq/free-models/groq-test-free/confirm",
                headers=headers, json={"acknowledged": True})
    draft = {"summary": "Actividad", "changes": [{"path": "index.html", "content": "<h1>Hola</h1>"}]}

    class Limited:
        async def stream(self, *_args):
            raise ProviderError("Cuota alcanzada", 429)
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

