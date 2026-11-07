import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func, inspect
from sqlalchemy.orm import Session

from educrea_api import db as db_module
from educrea_api.models import AiUsage, AiCredential, AiBudgetAlert, IncludedAiAccess, User
from educrea_api.services.ai import access, included, pricing
from educrea_api.services.ai.providers import registry
from educrea_api.config import Settings
from test_included_ai import account, settings, request_body, Stub
from conftest import engine


FLOWS = [
    ('proposals', request_body()), ('proposals/stream', request_body()),
    ('from-brief', {'provider': 'educrea'}), ('from-brief/stream', {'provider': 'educrea'}),
    ('dua', {'provider': 'educrea', 'path': 'index.html'}),
    ('dua/stream', {'provider': 'educrea', 'path': 'index.html'}),
    ('sections/stream', {'provider': 'educrea', 'sections': ['Evaluación']}),
]


def prepare_files(client, headers, project, endpoint):
    brief = {'title': 'Fracciones', 'kind': 'situacion' if endpoint.startswith('sections') else 'actividad',
             'language': 'es', 'level': 'primaria', 'instructions': 'Explica las fracciones'}
    for path, content in [('activity.json', json.dumps(brief)), ('index.html', '<h1>Fracciones</h1>')]:
        assert client.post(f'/api/projects/{project}/files', headers=headers,
                           json={'path': path, 'content': content}).status_code == 201


@pytest.mark.parametrize('state', ['not_invited', 'revoked'])
@pytest.mark.parametrize('endpoint,body', FLOWS)
def test_all_institutional_flows_deny_before_any_spend(client, settings, monkeypatch, state, endpoint, body):
    headers, project, user_id = account(client, invited=False)
    prepare_files(client, headers, project, endpoint)
    if state == 'revoked':
        with Session(engine) as db:
            access.set_access(db, user_id, authorized=True)
            access.set_access(db, user_id, authorized=False)
    calls = []
    monkeypatch.setattr(included, 'route', lambda *args: calls.append('route'))
    monkeypatch.setattr(included, 'adapter', lambda *args: calls.append('adapter'))
    response = client.post(f'/api/projects/{project}/ai/{endpoint}', headers=headers, json=body)
    if endpoint.endswith('/stream'):
        assert 'event: error' in response.text and '"status_code": 403' in response.text, response.text
        assert 'event: proposal' not in response.text
    else:
        assert response.status_code == 403, response.text
    assert 'invitación' in response.text
    assert calls == []
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AiUsage)) == 0
        assert db.scalar(select(func.count()).select_from(AiBudgetAlert)) == 0


@pytest.mark.parametrize('endpoint,body', FLOWS)
def test_all_institutional_flows_allow_invited_accounts(client, settings, monkeypatch, endpoint, body):
    headers, project, _ = account(client)
    prepare_files(client, headers, project, endpoint)
    content = json.dumps({'summary': 'Material', 'changes': [{
        'path': 'index.html', 'content': '<h1>Fracciones con ejemplos prácticos para comprender las partes de un todo.</h1>'}],
        'dua': {'barriers': [], 'measures': [{'principle': name, 'measure': 'Mejora de accesibilidad'}
                for name in ['representacion', 'accion_expresion', 'implicacion']]}})
    monkeypatch.setattr(included, 'adapter', lambda plan: Stub(text=content))
    response = client.post(f'/api/projects/{project}/ai/{endpoint}', headers=headers, json=body)
    if endpoint.endswith('/stream'):
        assert 'event: proposal' in response.text, response.text
    else:
        assert response.status_code == 201, response.text
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AiUsage)) == 1
        assert db.scalar(select(AiUsage)).actual_credits > 0


def test_registration_cannot_self_grant_and_status_is_private(client, settings):
    assert client.get('/api/ai/included').status_code == 401
    result = client.post('/api/auth/register', json={'email': 'new@example.org', 'password': 'test-password-123',
                          'included_ai_authorized': True, 'invited': True})
    assert result.status_code == 201
    assert result.json()['user']['included_ai_authorized'] is False
    status = client.get('/api/ai/included').json()
    assert status['authorized'] is False and status['access_status'] == 'not_invited'
    assert status['available'] is False
    assert 'qwen' not in json.dumps(status).lower() and 'deepseek' not in json.dumps(status).lower()
    with Session(engine) as db:
        assert db.scalar(select(IncludedAiAccess)) is None
    assert client.put('/api/ai/included/access', json={'authorized': True}).status_code == 404


def test_revocation_regrant_preserves_consumption_projects_and_keys(client, settings, monkeypatch):
    headers, project, user_id = account(client)
    client.put('/api/ai/providers/deepseek/key', headers=headers, json={'api_key': 'personal-test-deepseek'})
    with Session(engine) as db:
        ciphertext = db.scalar(select(AiCredential.ciphertext))
    monkeypatch.setattr(included, 'adapter', lambda plan: Stub())
    assert client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body()).status_code == 201
    used = client.get('/api/ai/included').json()['monthly_credits_used']
    with Session(engine) as db:
        access.set_access(db, user_id, authorized=False)
    assert client.get('/api/auth/me').json()['user']['included_ai_authorized'] is False
    # /me rotates CSRF; reload it before subsequent mutations.
    headers = {'X-CSRF-Token': client.get('/api/auth/me').json()['csrf_token']}
    assert client.get(f'/api/projects/{project}').status_code == 200
    assert client.get('/api/ai/included').json()['access_status'] == 'revoked'
    assert client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body()).status_code == 403
    with Session(engine) as db:
        access.set_access(db, user_id, authorized=True)
        assert db.scalar(select(AiCredential.ciphertext)) == ciphertext
        assert db.scalar(select(func.count()).select_from(IncludedAiAccess)) == 1
    assert client.get('/api/ai/included').json()['monthly_credits_used'] == used
    assert client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body()).status_code == 201
    assert client.get('/api/ai/included').json()['monthly_credits_used'] == used * 2


@pytest.mark.parametrize('state', ['not_invited', 'invited', 'revoked'])
@pytest.mark.parametrize('provider', ['openai', 'anthropic', 'deepseek', 'openrouter', 'groq', 'gemini', 'mistral'])
def test_byok_paid_remains_open_in_every_access_state(client, settings, monkeypatch, state, provider):
    from educrea_api.main import app
    from educrea_api.services.ai.providers.gemini import get_gemini_provider
    headers, project, user_id = account(client, invited=state != 'not_invited')
    if state == 'revoked':
        with Session(engine) as db:
            access.set_access(db, user_id, authorized=False)
    assert client.put(f'/api/ai/providers/{provider}/key', headers=headers,
                      json={'api_key': 'personal-test-provider'}).status_code == 204
    monkeypatch.setattr(pricing, 'get_settings', lambda: Settings(paid_models_json=json.dumps({
        provider: {'paid-test': {'input': 1000000, 'output': 2000000}}})))
    monkeypatch.setattr(registry, 'adapter', lambda name: Stub())
    app.dependency_overrides[get_gemini_provider] = lambda: Stub()
    monkeypatch.setattr(included, 'adapter', lambda *args: pytest.fail('BYOK must not use institutional keys'))
    body = {**request_body(), 'provider': provider, 'model': 'paid-test', 'mode': 'paid'}
    estimate = client.post(f'/api/projects/{project}/ai/estimate', headers=headers, json=body).json()
    client.put('/api/ai/budget', headers=headers, json={'monthly_limit_microusd': 1000000})
    response = client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json={**body,
        'paid_authorized': True, 'approved_max_cost_microusd': estimate['maximum_cost_microusd'],
        'approved_estimate_fingerprint': estimate['fingerprint']})
    assert response.status_code == 201, response.text
    with Session(engine) as db:
        assert list(db.scalars(select(AiUsage).where(AiUsage.mode == 'included'))) == []
    assert client.get('/api/ai/included').json()['monthly_credits_used'] == 0


def test_permission_is_rechecked_at_reservation_and_running_request_can_finish(client, settings):
    _, _, user_id = account(client)
    with Session(engine) as db:
        access.require_access(db, user_id)
        plan = included.route('qwen')
        access.set_access(db, user_id, authorized=False)
        with pytest.raises(HTTPException) as error:
            included.reserve(db, user_id, plan, 'JSON')
        assert error.value.status_code == 403
        access.set_access(db, user_id, authorized=True)
        identifier = included.reserve(db, user_id, plan, 'JSON')
        access.set_access(db, user_id, authorized=False)
        included.reconcile(db, identifier, {'input_tokens': 100, 'output_tokens': 50}, useful=True)
        assert db.get(AiUsage, identifier).status == 'completed'
        with pytest.raises(HTTPException):
            included.reserve(db, user_id, plan, 'JSON')


def test_server_cli_grant_status_revoke_and_missing_account(client, monkeypatch, capsys):
    _, _, user_id = account(client, invited=False)
    monkeypatch.setattr(db_module, 'SessionLocal', lambda: Session(engine))
    for action, expected in [('status', 'not_invited'), ('grant', 'invited'), ('grant', 'invited'), ('revoke', 'revoked')]:
        access.main([action, '--email', 'INCLUDED@example.org'])
        output = json.loads(capsys.readouterr().out)
        assert output == {'user_id': str(user_id), 'access_status': expected}
    with pytest.raises(SystemExit) as error:
        access.main(['grant', '--user-id', str(uuid4())])
    assert error.value.code == 1


def test_access_migration_is_reversible_and_never_auto_grants(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from educrea_api import config
    from sqlalchemy import create_engine, MetaData, Table
    url = 'sqlite:///' + str(tmp_path / 'access-migration.db')
    monkeypatch.setattr(config, 'get_settings', lambda: Settings(database_url=url))
    cfg = Config('alembic.ini')
    command.upgrade(cfg, '0013_included_ai')
    migration_engine = create_engine(url)
    users = Table('users', MetaData(), autoload_with=migration_engine)
    with migration_engine.begin() as conn:
        conn.execute(users.insert().values(id=uuid4().hex, email='existing@example.org', password_hash='unused',
                                          created_at=included.now_utc()))
    command.upgrade(cfg, 'head')
    with migration_engine.connect() as conn:
        grants = Table('included_ai_access', MetaData(), autoload_with=conn)
        assert conn.scalar(select(func.count()).select_from(grants)) == 0
    command.downgrade(cfg, '0013_included_ai')
    assert 'included_ai_access' not in inspect(migration_engine).get_table_names()
    with migration_engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(users)) == 1
    command.upgrade(cfg, 'head')
    migration_engine.dispose()


from test_included_ai import concurrency_database


def test_permission_rechecked_across_connections(concurrency_database, settings):
    from educrea_api.db import Base
    Base.metadata.create_all(concurrency_database)
    with Session(concurrency_database) as db:
        user = User(email='permission-race@example.org', password_hash='unused')
        db.add(user)
        db.commit()
        user_id = user.id
        access.set_access(db, user_id, authorized=True)
    with Session(concurrency_database) as reading:
        access.require_access(reading, user_id)
        with Session(concurrency_database) as revoking:
            access.set_access(revoking, user_id, authorized=False)
        with pytest.raises(HTTPException) as error:
            included.reserve(reading, user_id, included.route('qwen'), 'JSON')
        assert error.value.status_code == 403
        assert reading.scalar(select(func.count()).select_from(AiUsage)) == 0


def test_implicit_teacher_shortcut_keeps_byok_open_for_non_invited_user(client, settings, monkeypatch):
    from educrea_api.main import app
    from educrea_api.services.ai.providers.gemini import get_gemini_provider
    headers, project, _ = account(client, invited=False)
    prepare_files(client, headers, project, 'from-brief')
    client.put('/api/ai/providers/gemini/key', headers=headers, json={'api_key': 'personal-test-gemini'})
    assert client.post('/api/ai/providers/gemini/free-models/gemini-test-free/confirm', headers=headers,
                       json={'acknowledged': True}).status_code == 204
    app.dependency_overrides[get_gemini_provider] = lambda: Stub()
    monkeypatch.setattr(included, 'adapter', lambda *args: pytest.fail('No implicit institutional access'))
    response = client.post(f'/api/projects/{project}/ai/from-brief', headers=headers, json={})
    assert response.status_code == 201 and response.json()['provider'] == 'gemini'
