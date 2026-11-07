import json

from fastapi.testclient import TestClient

from educrea_api.main import app
from educrea_api.services.ai import engine, illustrations
from educrea_api.services.ai.providers.base import ProviderError, ProviderResult
from educrea_api.services.ai.providers.gemini import get_gemini_provider
from test_ai import setup_user

BRIEF = {"title": "El ciclo del agua", "language": "es", "level": "primaria",
         "instructions": "Tarjetas sobre evaporación, condensación y precipitación"}


def answer(count: int) -> str:
    return json.dumps({"summary": "Ilustraciones", "changes": [
        {"path": f"ilustracion-{i}", "content": f"ALT: Nube número {i}\nPROMPT: Una nube gris sobre un lago {i}, vista lateral"}
        for i in range(1, count + 1)]})


class Stub:
    def __init__(self, text: str):
        self.text, self.prompts = text, []

    async def generate(self, _key, _model, prompt):
        self.prompts.append(prompt)
        return ProviderResult(self.text, {"input_tokens": 10, "output_tokens": 20})


def project_with_brief(client: TestClient, illustrations_flag=True):
    headers, project_id = setup_user(client)
    response = client.post(f"/api/projects/{project_id}/template", headers=headers,
                           json={"template": "tarjetas", "brief": {**BRIEF, "illustrations": illustrations_flag}})
    assert response.status_code == 201
    return headers, project_id


def test_prompts_are_written_by_the_free_ai_with_style_and_safety(client: TestClient):
    headers, project_id = project_with_brief(client)
    stub = Stub(answer(3))
    app.dependency_overrides[get_gemini_provider] = lambda: stub
    response = client.post(f"/api/projects/{project_id}/ai/illustrations/prompts", headers=headers,
                           json={"count": 3, "style": "colorear"})
    assert response.status_code == 200
    items = response.json()
    assert [item["alt"] for item in items] == ["Nube número 1", "Nube número 2", "Nube número 3"]
    assert all(illustrations.STYLE_PROMPTS["colorear"] in item["prompt"] and illustrations.SAFETY in item["prompt"]
               for item in items)
    assert "exactamente 3 ilustraciones" in stub.prompts[0] and "El ciclo del agua" in stub.prompts[0]
    quota = client.get("/api/ai/quota").json()
    assert quota["requests_used"] == 1


def test_prompts_validate_input_and_need_a_free_ai(client: TestClient):
    headers, project_id = project_with_brief(client)
    route = f"/api/projects/{project_id}/ai/illustrations/prompts"
    assert client.post(route, headers=headers, json={"count": 7}).status_code == 422
    assert client.post(route, headers=headers, json={"count": 2, "style": "neon"}).status_code == 422
    assert client.post(route, json={"count": 2}).status_code == 403  # CSRF
    client.delete("/api/ai/providers/gemini/free-models/gemini-test-free/confirm", headers=headers)
    assert client.post(route, headers=headers, json={"count": 2}).status_code == 409


def test_unusable_answer_is_an_error_not_invented_prompts(client: TestClient):
    headers, project_id = project_with_brief(client)
    app.dependency_overrides[get_gemini_provider] = lambda: Stub(json.dumps(
        {"summary": "x", "changes": [{"path": "ilustracion-1", "content": "sin formato"}]}))
    response = client.post(f"/api/projects/{project_id}/ai/illustrations/prompts", headers=headers, json={"count": 1})
    assert response.status_code == 502


def test_saturated_provider_is_reported(client: TestClient):
    headers, project_id = project_with_brief(client)

    class Saturated:
        async def generate(self, *_args):
            raise ProviderError("saturado", 503)

    app.dependency_overrides[get_gemini_provider] = lambda: Saturated()
    response = client.post(f"/api/projects/{project_id}/ai/illustrations/prompts", headers=headers, json={"count": 1})
    assert response.status_code == 502 and "Ninguna IA gratuita" in response.json()["detail"]


def test_brief_flag_tells_the_first_version_to_place_the_images(client: TestClient):
    _headers, project_id = project_with_brief(client)
    base = f"/api/projects/{project_id}/files"
    file_id = next(item["id"] for item in client.get(base).json() if item["path"] == "activity.json")
    stored = json.loads(client.get(f"{base}/{file_id}").json()["content"])
    assert stored["illustrations"] is True
    assert engine.ILLUSTRATIONS_RULE in engine.instruction_for(stored)
    assert engine.ILLUSTRATIONS_RULE not in engine.instruction_for({**stored, "illustrations": "sí, por favor"})
