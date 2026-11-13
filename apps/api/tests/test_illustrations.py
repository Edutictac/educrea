import json

import pytest

from fastapi.testclient import TestClient

from educrea_api.main import app
from educrea_api.services.ai import engine, illustrations
from educrea_api.services.ai.providers.base import ProviderChunk, ProviderError, ProviderResult
from educrea_api.services.ai.providers.gemini import get_gemini_provider
from test_ai import setup_user

pytestmark = pytest.mark.skip(reason="Generación de imagen y vídeo desactivada en esta iteración; el código se conserva para reactivarla.")


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

    async def stream(self, _key, _model, prompt):
        self.prompts.append(prompt)
        yield ProviderChunk(text=self.text, usage={"input_tokens": 10, "output_tokens": 20}, finished=True)


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
    assert client.post(route, headers=headers, json={"count": 11}).status_code == 422
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


INFOGRAPHIC = ("<!doctype html><html lang=\"es\"><head><style>body{color:#000}</style></head><body><main>"
               "<h1>Historia de la música</h1><section class=\"step\"><svg><path d=\"M0 0\"/></svg>"
               "<h2>Edad Media</h2><p>Canto gregoriano &amp; trovadores</p></section></main></body></html>")


def infographic_project(client: TestClient):
    headers, project_id = setup_user(client)
    brief = {"title": "Historia de la música", "language": "es", "level": "secundaria", "instructions": "Épocas"}
    assert client.post(f"/api/projects/{project_id}/template", headers=headers,
                       json={"template": "infografia", "brief": brief}).status_code == 201
    assert client.post(f"/api/projects/{project_id}/files", headers=headers,
                       json={"path": "infografia.html", "content": INFOGRAPHIC}).status_code == 201
    return headers, project_id


def test_infographic_prompts_read_the_current_content_without_markup(client: TestClient):
    headers, project_id = infographic_project(client)
    stub = Stub(answer(2))
    app.dependency_overrides[get_gemini_provider] = lambda: stub
    response = client.post(f"/api/projects/{project_id}/ai/illustrations/prompts", headers=headers,
                           json={"count": 2, "from_content": True})
    assert response.status_code == 200 and len(response.json()) == 2
    sent = stub.prompts[0]
    assert "infografía" in sent and illustrations.INFOGRAPHIC_HINT in sent
    assert "Canto gregoriano & trovadores" in sent and "<svg" not in sent and "color:#000" not in sent
    # Without from_content only the brief is described, as in guided creation.
    client.post(f"/api/projects/{project_id}/ai/illustrations/prompts", headers=headers, json={"count": 1})
    assert "Contenido actual" not in stub.prompts[1]


def test_placement_inserts_the_new_images_with_history(client: TestClient):
    from test_ai import stream_events
    from test_assets import PNG, upload

    headers, project_id = infographic_project(client)
    base = f"/api/projects/{project_id}"
    asset = upload(client, base, headers, PNG, filename="ilustracion-1.png", alt="Un laúd medieval").json()
    route = f"{base}/ai/illustrations/place/stream"
    assert client.post(route, headers=headers, json={"paths": ["imagenes/no-existe.png"]}).status_code == 422
    assert client.post(route, headers=headers, json={"paths": []}).status_code == 422
    assert client.post(route, json={"paths": [asset["path"]]}).status_code == 403  # CSRF
    placed = INFOGRAPHIC.replace("<h2>Edad Media</h2>",
                                 f"<h2>Edad Media</h2><img src=\"{asset['path']}\" alt=\"Un laúd medieval\" class=\"ilustracion\">")
    stub = Stub(json.dumps({"summary": "Ilustrada", "changes": [{"path": "infografia.html", "content": placed}]}))
    app.dependency_overrides[get_gemini_provider] = lambda: stub
    events = stream_events(client.post(route, headers=headers, json={"paths": [asset["path"]]}))
    assert events[-1][0] == "proposal" and events[-1][1]["status"] == "applied"
    assert f"{asset['path']} (alt: Un laúd medieval)" in stub.prompts[0] and "infografia.html" in stub.prompts[0]
    files = {item["path"]: item["id"] for item in client.get(f"{base}/files").json()}
    assert asset["path"] in client.get(f"{base}/files/{files['infografia.html']}").json()["content"]


def test_placement_refuses_templates_without_image_field(client: TestClient):
    headers, project_id = setup_user(client)
    assert client.post(f"/api/projects/{project_id}/template", headers=headers,
                       json={"template": "sopa_letras", "brief": BRIEF}).status_code == 201
    response = client.post(f"/api/projects/{project_id}/ai/illustrations/place/stream", headers=headers,
                           json={"paths": ["imagenes/x.png"]})
    assert response.status_code == 409


def test_main_path_and_catalog_flag():
    assert illustrations.main_path({"kind": "ficha", "template": "ficha"}) == "ficha.md"
    assert illustrations.main_path({"kind": "situacion"}) == "situacion.md"
    assert illustrations.main_path({"kind": "actividad", "template": "infografia"}) == "infografia.html"
    assert illustrations.main_path({"kind": "actividad", "template": "tarjetas"}) == "datos.js"
    from educrea_api.services import templates
    flags = {item["id"]: item["illustrable"] for item in templates.catalog()}
    assert flags["infografia"] and flags["ficha"] and flags["tarjetas"]
    assert not flags["sopa_letras"] and not flags["crucigrama"] and not flags["escucha"]


def test_invited_account_without_own_ai_describes_with_ia_educrea(client: TestClient, monkeypatch):
    from test_included_ai import Stub as IncludedStub, account
    from pydantic import SecretStr
    from educrea_api.config import Settings
    from educrea_api.services.ai import included

    s = Settings(free_ai_enabled=True, qwen_api_key=SecretStr("institutional-qwen-test"), qwen_model="qwen-test",
                 qwen_input_cost_per_million="1", qwen_output_cost_per_million="2",
                 deepseek_api_key=SecretStr("institutional-deepseek-test"), deepseek_model="deepseek-test",
                 deepseek_input_cost_per_million="3", deepseek_output_cost_per_million="6",
                 free_ai_global_daily_budget_usd="10", free_ai_global_monthly_budget_usd="100")
    monkeypatch.setattr(included, "get_settings", lambda: s)
    from educrea_api.routers import ai as ai_router
    monkeypatch.setattr(ai_router.included, "get_settings", lambda: s)
    monkeypatch.setattr(included, "adapter", lambda plan: IncludedStub(answer(2)))
    headers, project_id, _ = account(client)
    assert client.post(f"/api/projects/{project_id}/template", headers=headers,
                       json={"template": "ficha", "brief": {**BRIEF, "language": "va"}}).status_code == 201
    response = client.post(f"/api/projects/{project_id}/ai/illustrations/prompts", headers=headers,
                           json={"count": 2, "from_content": True})
    assert response.status_code == 200, response.text
    assert len(response.json()) == 2
    assert client.get("/api/ai/included").json()["credits_used"] > 0
