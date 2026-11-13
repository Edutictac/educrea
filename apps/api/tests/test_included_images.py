import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from educrea_api.config import Settings
from educrea_api.main import app
from educrea_api.models import AiUsage
from educrea_api.services.ai import images as image_service, included
from educrea_api.services.ai.providers.base import ProviderError
from educrea_api.services.ai.providers.gemini_image import get_gemini_image_provider
from conftest import engine
from test_images import CATALOG, MODEL, StubImage
from test_included_ai import account

pytestmark = pytest.mark.skip(reason="Generación de imagen y vídeo desactivada en esta iteración; el código se conserva para reactivarla.")


PROMPT = {"prompt": "Un laúd medieval", "model": MODEL, "aspect_ratio": "1:1",
          "rights_acknowledged": True, "no_personal_data": True}


@pytest.fixture
def settings(monkeypatch):
    s = Settings(image_models_json=CATALOG, included_images_enabled=True, included_image_model=MODEL,
                 included_images_weekly_limit=2, included_images_global_daily_limit=10,
                 gemini_api_key=SecretStr("institutional-gemini-test"))
    monkeypatch.setattr(included, "get_settings", lambda: s)
    monkeypatch.setattr(image_service, "get_settings", lambda: s)
    return s


def test_invited_account_generates_with_the_institutional_key_and_weekly_quota(client: TestClient, settings):
    headers, project, user_id = account(client)
    status = client.get("/api/ai/images/models").json()
    assert status["configured"] is True and status["own_key"] is False and status["default"] == MODEL
    assert status["included"]["remaining"] == 2 and status["included"]["weekly_limit"] == 2
    assert client.get("/api/ai/included").json()["images"]["remaining"] == 2
    seen: list = []
    app.dependency_overrides[get_gemini_image_provider] = lambda: StubImage(key_seen=seen)
    route = f"/api/projects/{project}/ai/images"
    for _ in range(2):  # no paid confirmation: the teacher pays nothing
        response = client.post(route, headers=headers, json=PROMPT)
        assert response.status_code == 200, response.text
        assert response.json()["included"] is True and response.json()["cost_microusd"] == 0
    assert seen == ["institutional-gemini-test"] * 2
    assert "institutional-gemini" not in response.text
    assert client.get("/api/ai/images/models").json()["included"]["remaining"] == 0
    assert client.get("/api/ai/included").json()["images"]["remaining"] == 0
    exhausted = client.post(route, headers=headers, json=PROMPT)
    assert exhausted.status_code == 429 and "semana" in exhausted.json()["detail"]
    with Session(engine) as db:
        rows = list(db.scalars(select(AiUsage).where(AiUsage.user_id == user_id)))
        assert {(r.mode, r.task_type, r.status) for r in rows} == {("included", "image", "completed")}
        assert all(r.actual_credits == 0 and r.actual_cost_microusd > 0 for r in rows)
    # Images never use the teacher's credits nor the personal budget.
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == 0


def test_images_do_not_consume_text_request_limits(client: TestClient, settings):
    headers, project, _ = account(client)
    settings.free_ai_daily_request_limit = 1
    app.dependency_overrides[get_gemini_image_provider] = lambda: StubImage()
    assert client.post(f"/api/projects/{project}/ai/images", headers=headers, json=PROMPT).status_code == 200
    with Session(engine) as db:
        user = db.scalar(select(AiUsage.user_id))
        rows = list(db.scalars(select(AiUsage).where(AiUsage.user_id == user, included.NOT_IMAGE)))
        assert rows == []


def test_rejection_gives_the_slot_back_and_unknown_spend_keeps_it(client: TestClient, settings):
    headers, project, _ = account(client)
    route = f"/api/projects/{project}/ai/images"

    class Failing:
        def __init__(self, consumed: bool):
            self.consumed = consumed

        async def generate(self, *_args, **_kwargs):
            error = ProviderError("cuota", 429)
            error.consumed_unknown = self.consumed
            raise error

    app.dependency_overrides[get_gemini_image_provider] = lambda: Failing(False)
    response = client.post(route, headers=headers, json=PROMPT)
    assert response.status_code == 429 and "IA EduCrea" in response.json()["detail"]
    assert client.get("/api/ai/images/models").json()["included"]["remaining"] == 2
    app.dependency_overrides[get_gemini_image_provider] = lambda: Failing(True)
    client.post(route, headers=headers, json=PROMPT)
    assert client.get("/api/ai/images/models").json()["included"]["remaining"] == 1


def test_global_daily_limit_and_switches(client: TestClient, settings):
    headers, project, _ = account(client)
    settings.included_images_global_daily_limit = 1
    app.dependency_overrides[get_gemini_image_provider] = lambda: StubImage()
    route = f"/api/projects/{project}/ai/images"
    assert client.post(route, headers=headers, json=PROMPT).status_code == 200
    blocked = client.post(route, headers=headers, json=PROMPT)
    assert blocked.status_code == 429 and "hoy" in blocked.json()["detail"]
    settings.included_images_enabled = False
    status = client.get("/api/ai/images/models").json()
    assert status["included"] is None and status["configured"] is False


def test_not_invited_accounts_keep_byok(client: TestClient, settings):
    headers, project, _ = account(client, invited=False)
    status = client.get("/api/ai/images/models").json()
    assert status["included"] is None and status["configured"] is False
    response = client.post(f"/api/projects/{project}/ai/images", headers=headers, json=PROMPT)
    assert response.status_code == 403  # paid confirmation required on the BYOK path


def test_model_outside_the_catalog_disables_included_images(settings):
    settings.included_image_model = "gemini-not-in-catalog"
    assert included.image_model() is None
    settings.included_image_model = MODEL
    settings.gemini_api_key = None
    assert included.image_model() is None


def test_admin_override_replaces_the_environment_image_quota(client: TestClient, settings):
    headers, project, _ = account(client)
    with Session(engine) as db:
        included.set_image_limits(db, 1, 1)
    status = client.get("/api/ai/images/models").json()
    assert status["included"]["weekly_limit"] == 1 and status["included"]["remaining"] == 1
    settings.included_images_weekly_limit = 5  # once saved, the administrator value wins over the environment
    app.dependency_overrides[get_gemini_image_provider] = lambda: StubImage()
    route = f"/api/projects/{project}/ai/images"
    assert client.post(route, headers=headers, json=PROMPT).status_code == 200
    blocked = client.post(route, headers=headers, json=PROMPT)
    assert blocked.status_code == 429 and "semana" in blocked.json()["detail"]
