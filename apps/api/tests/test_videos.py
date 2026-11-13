import asyncio
import base64
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from educrea_api.config import Settings
from educrea_api.main import app
from educrea_api.models import AiUsage
from educrea_api.services.ai import videos as video_service
from educrea_api.services.ai.providers.base import ProviderError
from educrea_api.services.ai.providers.gemini_video import (
    GeminiVideoProvider, GeneratedVideo, get_gemini_video_provider)
from test_ai import setup_user
from test_auth_projects import register
from conftest import engine

pytestmark = pytest.mark.skip(reason="Generación de imagen y vídeo desactivada en esta iteración; el código se conserva para reactivarla.")


MODEL = "gemini-omni-1.2-flash"
CATALOG = json.dumps({"gemini": {MODEL: {
    "360p": {"second_microusd": 23000},
    "720p": {"second_microusd": 70000},
    "input_microusd_per_million": 1500000,
}}})
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64


@pytest.fixture
def videos(monkeypatch):
    settings = Settings(video_models_json=CATALOG, ai_daily_video_requests=5)
    monkeypatch.setattr(video_service, "get_settings", lambda: settings)
    return settings


class StubVideo:
    def __init__(self, data: bytes = MP4, key_seen: list | None = None):
        self.data = data
        self.key_seen = key_seen if key_seen is not None else []

    async def generate(self, api_key, model, prompt, aspect_ratio="16:9", resolution="360p", duration=6):
        self.key_seen.append(api_key)
        return GeneratedVideo(self.data, "video/mp4")


def budget(client: TestClient, headers: dict, micro_usd: int = 1000000):
    assert client.put("/api/ai/budget", headers=headers,
                      json={"monthly_limit_microusd": micro_usd}).status_code == 200


def estimate(client: TestClient, headers: dict, project_id: str, duration: int = 6,
             resolution: str = "360p"):
    response = client.post(f"/api/projects/{project_id}/ai/videos/estimate", headers=headers,
                           json={"prompt": "Una mariposa volando entre flores", "model": MODEL,
                                 "resolution": resolution, "duration": duration, "aspect_ratio": "16:9"})
    assert response.status_code == 200, response.text
    return response.json()


def body(est: dict, **extra):
    return {"prompt": "Una mariposa volando entre flores", "model": MODEL, "resolution": "360p",
            "duration": 6, "aspect_ratio": "16:9", "paid_authorized": True,
            "approved_max_cost_microusd": est["maximum_cost_microusd"],
            "approved_estimate_fingerprint": est["fingerprint"],
            "rights_acknowledged": True, "no_personal_data": True, **extra}


def test_video_catalog_estimate_and_models(client: TestClient, videos):
    headers, project_id = setup_user(client)
    data = estimate(client, headers, project_id)
    assert data["second_microusd"] == 23000 and data["duration"] == 6
    assert data["maximum_cost_microusd"] == 138000 + data["input_microusd"]
    assert len(data["fingerprint"]) == 64
    payload = client.get("/api/ai/videos/models").json()
    assert payload["default"] == MODEL and payload["default_resolution"] == "360p"
    assert payload["configured"] is True


def test_video_generate_preview_accounting_and_save(client: TestClient, videos):
    headers, project_id = setup_user(client)
    budget(client, headers)
    est = estimate(client, headers, project_id)
    seen: list[str] = []
    app.dependency_overrides[get_gemini_video_provider] = lambda: StubVideo(key_seen=seen)
    response = client.post(f"/api/projects/{project_id}/ai/videos", headers=headers, json=body(est))
    assert response.status_code == 200, response.text
    result = response.json()
    raw = base64.b64decode(result["video_base64"])
    assert raw[4:8] == b"ftyp"
    assert result["cost_microusd"] == est["maximum_cost_microusd"]
    assert result["suggested_credit"].startswith("Generado con IA (Google Gemini")
    assert seen == ["test-only-gemini-key"]
    assert client.get(f"/api/projects/{project_id}/videos").json() == []
    saved = client.post(f"/api/projects/{project_id}/videos",
                        headers={**headers, "Content-Type": "application/octet-stream"},
                        params={"filename": result["suggested_filename"], "description": "Mariposa",
                                "credit": result["suggested_credit"], "duration": 6, "resolution": "360p"},
                        content=raw)
    assert saved.status_code == 201, saved.text
    video = saved.json()
    assert video["path"] == "videos/video-ia.mp4" and video["duration_seconds"] == 6
    listed = client.get(f"/api/projects/{project_id}/videos").json()
    assert listed[0]["description"] == "Mariposa"
    content = client.get(f"/api/projects/{project_id}/videos/{video['id']}/content")
    assert content.status_code == 200 and content.headers["content-type"] == "video/mp4"
    assert content.content == raw
    assert client.delete(f"/api/projects/{project_id}/videos/{video['id']}", headers=headers).status_code == 204
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == est["maximum_cost_microusd"]


def test_video_confirmation_rights_and_failed_refund(client: TestClient, videos):
    headers, project_id = setup_user(client)
    budget(client, headers)
    est = estimate(client, headers, project_id)
    assert client.post(f"/api/projects/{project_id}/ai/videos", headers=headers,
                       json={**body(est), "paid_authorized": False}).status_code == 403
    assert client.post(f"/api/projects/{project_id}/ai/videos", headers=headers,
                       json={**body(est), "rights_acknowledged": False}).status_code == 422
    assert client.post(f"/api/projects/{project_id}/ai/videos", headers=headers,
                       json={**body(est), "approved_max_cost_microusd": 1}).status_code == 403

    class Failing:
        async def generate(self, *args):
            raise ProviderError("sin vídeo", 429)

    app.dependency_overrides[get_gemini_video_provider] = lambda: Failing()
    assert client.post(f"/api/projects/{project_id}/ai/videos", headers=headers, json=body(est)).status_code == 429
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == 0
    with Session(engine) as db:
        row = db.scalar(select(AiUsage))
        assert row.status == "failed" and row.actual_cost_microusd == 0


@pytest.mark.parametrize("failure", ["timeout", "unusable"])
def test_video_possibly_billed_failures_keep_counting_against_the_budget(client: TestClient, videos, failure):
    headers, project_id = setup_user(client)
    budget(client, headers, 10000000)
    est = estimate(client, headers, project_id)

    class TimedOut:
        async def generate(self, *args):
            raise ProviderError("tardó demasiado", 504, consumed_unknown=True)

    # «unusable»: Google delivered (and billed) bytes that are not a valid video.
    app.dependency_overrides[get_gemini_video_provider] = (
        (lambda: TimedOut()) if failure == "timeout" else (lambda: StubVideo(data=b"not a video")))
    response = client.post(f"/api/projects/{project_id}/ai/videos", headers=headers, json=body(est))
    assert response.status_code >= 400
    assert client.get("/api/ai/budget").json()["spent_or_reserved_microusd"] == est["maximum_cost_microusd"]
    with Session(engine) as db:
        row = db.scalar(select(AiUsage))
        assert row.status == "failed" and row.actual_cost_microusd == est["maximum_cost_microusd"]


def test_video_guest_temporary_key_and_daily_limit(client: TestClient, videos):
    videos.ai_daily_video_requests = 1
    opened = client.post("/api/auth/guest")
    csrf = opened.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}
    project = client.post("/api/projects", headers=headers, json={"title": "Vídeo invitado"}).json()["id"]
    budget(client, headers)
    temporary = {"X-Educrea-Temporary-Keys": json.dumps({
        "gemini": {"key": "temporary-gemini-key-123", "confirmed": []}})}
    est = estimate(client, {**temporary, **headers}, project)
    seen: list[str] = []
    app.dependency_overrides[get_gemini_video_provider] = lambda: StubVideo(key_seen=seen)
    first = client.post(f"/api/projects/{project}/ai/videos", headers={**temporary, **headers}, json=body(est))
    assert first.status_code == 200, first.text
    assert seen == ["temporary-gemini-key-123"]
    assert client.post(f"/api/projects/{project}/ai/videos", headers={**temporary, **headers},
                       json=body(est)).status_code == 429

    client.post("/api/auth/logout", headers=headers)
    register(client, "video-no-key@example.org")
    csrf = client.get("/api/auth/me").json()["csrf_token"]
    project = client.post("/api/projects", headers={"X-CSRF-Token": csrf}, json={"title": "Sin clave"}).json()["id"]
    budget(client, {"X-CSRF-Token": csrf})
    est = estimate(client, {"X-CSRF-Token": csrf}, project)
    assert client.post(f"/api/projects/{project}/ai/videos", headers={"X-CSRF-Token": csrf},
                       json=body(est)).status_code == 409


def test_video_adapter_request_and_errors():
    async def run():
        seen = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            seen["key"] = request.headers["x-goog-api-key"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"steps": [
                {"type": "model_output", "content": [
                    {"type": "video", "mime_type": "video/mp4", "data": base64.b64encode(MP4).decode()}]}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await GeminiVideoProvider(client).generate(
                "test-key", MODEL, "Una mariposa", "9:16", "720p", 5)
            assert result.data == MP4 and result.media_type == "video/mp4"
            assert seen["body"]["response_format"]["resolution"] == "720p"
            assert seen["body"]["response_format"]["duration"] == "5s"
            assert seen["body"]["response_format"]["aspect_ratio"] == "9:16"

        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(429, json={"error": "quota"}))) as client:
            with pytest.raises(ProviderError) as error:
                await GeminiVideoProvider(client).generate("test-key", MODEL, "Una mariposa")
            assert error.value.status_code == 429

    asyncio.run(run())


def test_editable_video_limits_are_enforced_and_reported_per_account(client, videos):
    from educrea_api.models import User
    headers, project_id = setup_user(client)
    with Session(engine) as db:
        user = db.scalar(select(User))
        user.is_admin = True
        db.commit()
    limits = '/api/admin/beta/video-limits'
    assert client.put(limits, headers=headers, json={'daily_limit': 1, 'global_daily_limit': 1}).status_code == 200
    videos.ai_daily_video_requests = 99  # the persisted override must win
    budget(client, headers)
    est = estimate(client, headers, project_id)
    app.dependency_overrides[get_gemini_video_provider] = lambda: StubVideo()
    quota = client.get('/api/ai/included').json()['videos']
    assert quota['remaining'] == 1 and quota['daily_limit'] == 1
    assert client.post(f'/api/projects/{project_id}/ai/videos', headers=headers, json=body(est)).status_code == 200
    quota = client.get('/api/ai/videos/models').json()['quota']
    assert quota['remaining'] == 0 and quota['used'] == 1
    assert client.get('/api/ai/included').json()['videos']['remaining'] == 0
    assert client.post(f'/api/projects/{project_id}/ai/videos', headers=headers, json=body(est)).status_code == 429
    # A second account has its own allowance, but cannot bypass the shared cap.
    client.cookies.clear()
    other_headers = {'X-CSRF-Token': register(client, 'other-video@example.org')}
    other_project = client.post('/api/projects', headers=other_headers, json={'title': 'Otro vídeo'}).json()['id']
    assert client.put('/api/ai/providers/gemini/key', headers=other_headers,
                      json={'api_key': 'test-only-gemini-key'}).status_code == 204
    budget(client, other_headers)
    other_est = estimate(client, other_headers, other_project)
    quota = client.get('/api/ai/included').json()['videos']
    assert quota['remaining'] == 1 and quota['used'] == 0 and quota['available_remaining'] == 0
    denied = client.post(f'/api/projects/{other_project}/ai/videos', headers=other_headers, json=body(other_est))
    assert denied.status_code == 429 and 'instalación' in denied.json()['detail']


def test_zero_video_limit_blocks_generation_without_calling_provider(client, videos):
    from educrea_api.models import User
    headers, project = setup_user(client)
    with Session(engine) as db:
        user = db.scalar(select(User))
        user.is_admin = True
        db.commit()
    assert client.put('/api/admin/beta/video-limits', headers=headers,
                      json={'daily_limit': 0, 'global_daily_limit': 0}).status_code == 200
    budget(client, headers)
    est = estimate(client, headers, project)
    seen = []
    app.dependency_overrides[get_gemini_video_provider] = lambda: StubVideo(key_seen=seen)
    assert client.post(f'/api/projects/{project}/ai/videos', headers=headers, json=body(est)).status_code == 429
    assert not seen
    assert client.get('/api/ai/budget').json()['spent_or_reserved_microusd'] == 0


def test_video_quota_resets_at_utc_midnight_and_global_zero_is_unlimited(client, videos, monkeypatch):
    from datetime import datetime, timedelta, timezone
    headers, project = setup_user(client)
    budget(client, headers)
    est = estimate(client, headers, project)
    app.dependency_overrides[get_gemini_video_provider] = lambda: StubVideo()
    assert client.post(f'/api/projects/{project}/ai/videos', headers=headers, json=body(est)).status_code == 200
    quota = client.get('/api/ai/videos/models').json()['quota']
    assert quota['used'] == 1 and quota['available_remaining'] == 4
    tomorrow = datetime.fromisoformat(quota['renews_at'])
    assert tomorrow.hour == tomorrow.minute == 0 and tomorrow.utcoffset() == timedelta(0)
    with Session(engine) as db:
        row = db.scalar(select(AiUsage))
        row.created_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    assert client.get('/api/ai/included').json()['videos']['remaining'] == 5


def test_video_limits_migration_preserves_image_limits_and_is_reversible(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text, inspect
    from educrea_api import config
    url = 'sqlite:///' + str(tmp_path / 'video-limits.db')
    monkeypatch.setattr(config, 'get_settings', lambda: Settings(database_url=url))
    cfg = Config('alembic.ini')
    command.upgrade(cfg, '0021_included_ai_limits')
    migration_engine = create_engine(url)
    with migration_engine.begin() as conn:
        conn.execute(text("INSERT INTO included_ai_limits (id, images_weekly_limit, images_global_daily_limit, updated_at) VALUES (1, 3, 20, CURRENT_TIMESTAMP)"))
    command.upgrade(cfg, '0022_video_limits')
    with migration_engine.connect() as conn:
        row = conn.execute(text('SELECT images_weekly_limit, videos_daily_limit FROM included_ai_limits')).one()
        assert tuple(row) == (3, None)
    command.downgrade(cfg, '0021_included_ai_limits')
    assert 'videos_daily_limit' not in {c['name'] for c in inspect(migration_engine).get_columns('included_ai_limits')}
    with migration_engine.connect() as conn:
        assert conn.scalar(text('SELECT images_weekly_limit FROM included_ai_limits')) == 3
    command.upgrade(cfg, '0022_video_limits')
    migration_engine.dispose()
