import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from educrea_api.services.ai import pricing
from educrea_api.services.ai.providers import registry
from educrea_api.services.ai.providers.base import ProviderError
from educrea_api.services.ai.providers.compatible import CompatibleProvider
from test_ai import setup_user


def test_deepseek_credentials_and_paid_only_access(client: TestClient):
    headers, project_id = setup_user(client)
    route = "/api/ai/providers/deepseek"
    assert client.get(route).json() == {
        "configured": False, "verified_free_models": [], "confirmed_free_models": [], "paid_models": []}
    assert client.put(f"{route}/key", json={"api_key": "test-deepseek-key"}).status_code == 403
    assert client.put(f"{route}/key", headers=headers,
                      json={"api_key": "test-deepseek-key"}).status_code == 204
    assert client.get(route).json()["configured"]
    assert "test-deepseek-key" not in client.get("/api/ai/providers").text
    assert client.post(f"{route}/free-models/deepseek-flash/confirm", headers=headers,
                       json={"acknowledged": True}).status_code == 403
    assert client.post(f"/api/projects/{project_id}/ai/proposals", headers=headers, json={
        "instruction": "Crea una actividad de fracciones", "provider": "deepseek",
        "model": "deepseek-flash", "mode": "free"}).status_code == 503
    assert "deepseek" not in registry.FREE_PROVIDERS
    assert registry.adapter("deepseek").url == "https://api.deepseek.com/chat/completions"
    assert client.delete(f"{route}/key", headers=headers).status_code == 204
    assert not client.get(route).json()["configured"]


def test_deepseek_generate_and_stream_usage():
    def handler(request):
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-deepseek-key"
        payload = json.loads(request.content)
        assert payload["model"] == "deepseek-flash"
        assert payload["max_tokens"] == pricing.MAX_OUTPUT_TOKENS
        assert payload["thinking"] == {"type": "disabled"}
        usage = {"prompt_tokens": 20, "completion_tokens": 30, "prompt_cache_hit_tokens": 10}
        if not payload["stream"]:
            return httpx.Response(200, json={"choices": [
                {"message": {"content": "{}"}, "finish_reason": "stop"}], "usage": usage})
        assert payload["stream_options"] == {"include_usage": True}
        return httpx.Response(200, text='\n'.join([
            ': keep-alive',
            'data: ' + json.dumps({"choices": [{"delta": {"content": "{}"}}]}),
            'data: ' + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": usage}),
            'data: [DONE]', '',
        ]))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = CompatibleProvider("deepseek", client)
            result = await provider.generate("test-deepseek-key", "deepseek-flash", "Produce JSON")
            assert result.text == "{}"
            assert result.usage == {"input_tokens": 20, "output_tokens": 30}
            chunks = [chunk async for chunk in provider.stream(
                "test-deepseek-key", "deepseek-flash", "Produce JSON")]
            assert ''.join(chunk.text for chunk in chunks) == "{}"
            assert chunks[-1].finished
            assert chunks[-1].usage == result.usage
    asyncio.run(run())


@pytest.mark.parametrize("status", [401, 429, 503])
def test_deepseek_errors_do_not_expose_credentials(status):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda _request: httpx.Response(status, text="test-deepseek-key"))) as client:
            provider = CompatibleProvider("deepseek", client)
            for streaming in (False, True):
                with pytest.raises(ProviderError) as error:
                    if streaming:
                        async for _ in provider.stream("test-deepseek-key", "deepseek-flash", "JSON"):
                            pass
                    else:
                        await provider.generate("test-deepseek-key", "deepseek-flash", "JSON")
                assert "test-deepseek-key" not in str(error.value)
                assert error.value.status_code == (502 if status == 401 else status)
    asyncio.run(run())
