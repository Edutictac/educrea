import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from educrea_api.config import Settings
from educrea_api.db import Base
from educrea_api.models import AiUsage, AiCredential, AiBudgetAlert, User
from educrea_api.services.ai import included, quotas, access
from educrea_api.services.ai.routing import TaskContext, DeterministicRouter
from educrea_api.services.ai.providers.base import ProviderChunk, ProviderResult, ProviderError
from test_auth_projects import register
from conftest import engine


@pytest.fixture
def settings(monkeypatch):
    s = Settings(free_ai_enabled=True, qwen_api_key=SecretStr('institutional-qwen-test'),
        deepseek_api_key=SecretStr('institutional-deepseek-test'), qwen_model='qwen-test', deepseek_model='deepseek-test',
        qwen_input_cost_per_million='1', qwen_output_cost_per_million='2',
        deepseek_input_cost_per_million='3', deepseek_output_cost_per_million='6',
        free_ai_global_daily_budget_usd='10', free_ai_global_monthly_budget_usd='100')
    monkeypatch.setattr(included, 'get_settings', lambda: s)
    return s


def account(client, invited=True):
    csrf = register(client, 'included@example.org')
    headers = {'X-CSRF-Token': csrf}
    project = client.post('/api/projects', headers=headers, json={'title': 'Material educativo'}).json()['id']
    with Session(engine) as db:
        user_id = db.scalar(select(User.id))
        if invited:
            access.set_access(db, user_id, authorized=True)
    return headers, project, user_id


def request_body(task='general'):
    return {'instruction': 'Crea una explicación de las fracciones', 'provider': 'educrea', 'mode': 'included',
            'automatic': True, 'task_type': task}


class Stub:
    def __init__(self, text=None, usage=None):
        self.text = text or json.dumps({'summary': 'Material', 'changes': [{'path': 'guia.md', 'content': '# Fracciones\nTexto'}]})
        self.usage = {'input_tokens': 100, 'output_tokens': 50} if usage is None else usage

    async def generate(self, *args):
        return ProviderResult(self.text, self.usage)

    async def stream(self, *args):
        yield ProviderChunk(text=self.text)
        yield ProviderChunk(usage=self.usage, finished=True)


@pytest.mark.parametrize('context,expected', [
    *[(TaskContext(task_type=task), 'qwen') for task in ('rubric', 'quiz', 'translation', 'unknown', 'json', 'planning')],
    *[(TaskContext(task_type=task), 'deepseek') for task in ('html', 'javascript', 'interactive-game', 'debugging', 'threejs')],
    (TaskContext(output_type='html'), 'deepseek'), (TaskContext(generator_type='interactive-app'), 'deepseek'),
    (TaskContext(project_kind='actividad'), 'deepseek'), (TaskContext(project_kind='situacion'), 'qwen'),
    (TaskContext(project_kind='actividad', template='quiz'), 'qwen'),
    (TaskContext(task_type='teacher-guide', project_kind='actividad'), 'qwen'),
])
def test_routing(context, expected):
    assert DeterministicRouter().select(context) == expected


def test_router_is_replaceable_without_gateway_changes(client, settings, monkeypatch):
    from educrea_api.routers import ai
    headers, project, _ = account(client)
    seen = []
    class Replacement:
        def select(self, context):
            seen.append(context)
            return 'qwen'
    monkeypatch.setattr(ai, 'get_router', lambda: Replacement())
    monkeypatch.setattr(included, 'adapter', lambda plan: Stub())
    assert client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body('code')).status_code == 201
    assert seen[0].task_type == 'code'


def test_weighted_credits_and_rounding(settings):
    qwen, deep = included.route('qwen'), included.route('deepseek')
    assert included.credits(included.cost(1000, 1000, qwen.price), 100000) == 300
    assert included.credits(included.cost(1000, 1000, deep.price), 100000) == 900
    assert included.cost(1000, 0, qwen.price) == 1000
    assert included.cost(0, 1000, qwen.price) == 2000
    assert included.credits(1, 100000) == 1
    assert included.credits(10, 100000) == 1
    assert included.credits(11, 100000) == 2
    assert included.credits(0, 100000, 3) == 3


def test_registered_user_shared_monthly_quota_no_key_and_private_responses(client, settings, monkeypatch):
    headers, project, user_id = account(client)
    selected = []
    def adapter(plan):
        selected.append(plan.provider)
        return Stub()
    monkeypatch.setattr(included, 'adapter', adapter)
    before = client.get('/api/ai/included').json()
    assert before['monthly_credits_used'] == 0
    for task, expected in [('general', 20), ('code', 80), ('teacher-guide', 100)]:
        response = client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body(task))
        assert response.status_code == 201, response.text
        assert response.json()['provider'] == 'educrea'
        assert response.json()['model'] == '' and response.json()['usage'] == {}
        assert client.get('/api/ai/included').json()['monthly_credits_used'] == expected
        assert 'institutional-' not in response.text
    assert selected == ['qwen', 'deepseek', 'qwen']
    assert 'qwen' not in client.get('/api/ai/included').text.lower()
    with Session(engine) as db:
        assert db.scalar(select(AiCredential)) is None
        rows = list(db.scalars(select(AiUsage).where(AiUsage.user_id == user_id)))
        assert {r.mode for r in rows} == {'included'}
        assert {r.provider for r in rows} == {'qwen', 'deepseek'}
    assert client.get('/api/ai/budget').json()['spent_or_reserved_microusd'] == 0
    assert client.get('/api/ai/quota').json()['requests_used'] == 0


def test_streaming_masks_providers_and_model_and_accounts(client, settings, monkeypatch):
    headers, project, _ = account(client)
    monkeypatch.setattr(included, 'adapter', lambda plan: Stub())
    response = client.post(f'/api/projects/{project}/ai/proposals/stream', headers=headers, json=request_body('code'))
    assert response.status_code == 200
    assert 'event: proposal' in response.text
    assert 'qwen' not in response.text and 'deepseek' not in response.text
    assert 'institutional-' not in response.text
    assert client.get('/api/ai/included').json()['monthly_credits_used'] == 60


def test_auth_csrf_and_ownership(client, settings):
    assert client.get('/api/ai/included').status_code == 401
    headers, project, _ = account(client)
    assert client.post(f'/api/projects/{project}/ai/proposals', json=request_body()).status_code == 403
    client.post('/api/auth/logout', headers=headers)
    csrf = register(client, 'other-included@example.org')
    assert client.post(f'/api/projects/{project}/ai/proposals', headers={'X-CSRF-Token': csrf},
                       json=request_body()).status_code == 404
    assert client.get('/api/ai/included/history').json() == []


def test_new_month_preserves_history_and_boundary_reservation(client, settings, monkeypatch):
    _, _, user_id = account(client)
    monkeypatch.setattr(included, 'now_utc', lambda: datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc))
    with Session(engine) as db:
        identifier = included.reserve(db, user_id, included.route('qwen'), 'JSON')
        monkeypatch.setattr(included, 'now_utc', lambda: datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc))
        included.reconcile(db, identifier, {'input_tokens': 100, 'output_tokens': 50}, useful=True)
        assert included.summary(db, user_id)['monthly_credits_used'] == 0
        assert included.summary(db, user_id)['renews_at'].startswith('2027-01-01')
        assert included.history(db, user_id) == [{'period_key': '2026-11', 'credits_used': 20}]
        second = included.reserve(db, user_id, included.route('deepseek'), 'JSON')
        included.reconcile(db, second, {'input_tokens': 100, 'output_tokens': 50}, useful=True)
        assert included.summary(db, user_id)['monthly_credits_used'] == 60
        assert len(included.history(db, user_id)) == 2


@pytest.mark.parametrize('actual,expected', [(60, 60), (0, 0), (110, 100)])
def test_reservation_refund_failure_and_controlled_overrun(client, settings, actual, expected):
    _, _, user_id = account(client)
    with Session(engine) as db:
        identifier = included.reserve(db, user_id, included.route('qwen'), 'JSON')
        row = db.get(AiUsage, identifier)
        row.reserved_credits = 100
        row.input_rate_microusd = 1000000
        row.output_rate_microusd = 1000000
        db.commit()
        included.reconcile(db, identifier, {'input_tokens': actual * 10, 'output_tokens': 0}, useful=bool(actual))
        assert included.summary(db, user_id)['monthly_credits_used'] == expected
        row = db.get(AiUsage, identifier)
        assert row.actual_cost_microusd == actual * 10
        included.reconcile(db, identifier, {'input_tokens': 999999, 'output_tokens': 0}, useful=True)
        assert included.summary(db, user_id)['monthly_credits_used'] == expected


def test_no_credit_missing_configuration_and_kill_switches(client, settings, monkeypatch):
    headers, project, _ = account(client)
    calls = []
    monkeypatch.setattr(included, 'adapter', lambda plan: calls.append(plan) or Stub())
    for field, value, status in [('free_ai_monthly_credits', 0, 429), ('free_ai_enabled', False, 503),
                                ('qwen_enabled', False, 503), ('qwen_input_cost_per_million', '0', 503),
                                ('qwen_base_url', 'http://invalid.test', 503)]:
        old = getattr(settings, field)
        setattr(settings, field, value)
        response = client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body())
        assert response.status_code == status, response.text
        setattr(settings, field, old)
    assert calls == []


@pytest.mark.parametrize('field,limit', [('free_ai_minute_request_limit', 1), ('free_ai_hourly_request_limit', 1),
                                      ('free_ai_daily_request_limit', 1)])
def test_rate_limits_global_per_user(client, settings, monkeypatch, field, limit):
    headers, project, _ = account(client)
    setattr(settings, field, limit)
    monkeypatch.setattr(included, 'adapter', lambda plan: Stub())
    assert client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body()).status_code == 201
    assert client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body('code')).status_code == 429


def test_input_and_context_limits(client, settings, monkeypatch):
    headers, project, _ = account(client)
    settings.free_ai_max_input_tokens = 10
    response = client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body())
    assert response.status_code == 413
    settings.free_ai_max_input_tokens = 32768
    settings.free_ai_max_context_tokens = 1
    response = client.post(f'/api/projects/{project}/ai/proposals/stream', headers=headers, json=request_body())
    assert '"status_code": 413' in response.text


def test_global_budget_reservations_alerts_and_metrics(client, settings):
    _, _, user_id = account(client)
    settings.free_ai_global_monthly_budget_usd = '0.010'
    settings.free_ai_global_daily_budget_usd = '1'
    with Session(engine) as db:
        other = User(email='budget-other@example.org', password_hash='unused')
        db.add(other)
        db.commit()
        other_id = other.id
        access.set_access(db, other_id, authorized=True)
        first = included.reserve(db, user_id, included.route('qwen'), 'JSON')
        assert {a.threshold for a in db.scalars(select(AiBudgetAlert))} == {50, 75, 90}
        with pytest.raises(HTTPException) as error:
            included.reserve(db, other_id, included.route('qwen'), 'JSON')
        assert error.value.status_code == 503
        included.reconcile(db, first, useful=False)
        assert included.metrics(db)['estimated_cost_microusd'] == 0
        second = included.reserve(db, other_id, included.route('qwen'), 'JSON')
        included.reconcile(db, second, {'input_tokens': 10000, 'output_tokens': 0}, useful=True)
        assert {a.threshold for a in db.scalars(select(AiBudgetAlert))} == {50, 75, 90, 100}
        assert not included.summary(db, other_id)['available']
        assert included.metrics(db)['providers']['qwen']['requests'] == 2


@pytest.fixture(params=['sqlite', 'postgresql'])
def concurrency_database(request, tmp_path):
    if request.param == 'sqlite':
        test_engine = create_engine('sqlite:///' + str(tmp_path / 'race.db'), connect_args={'timeout': 15})
        yield test_engine
        test_engine.dispose()
        return
    url = os.environ.get('EDUCREA_TEST_POSTGRES_URL')
    if not url:
        pytest.skip('EDUCREA_TEST_POSTGRES_URL not configured')
    schema = 'included_test_' + uuid4().hex
    from sqlalchemy import text
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    test_engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        yield test_engine
    finally:
        test_engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()


@pytest.mark.parametrize('scope', ['user', 'global'])
@pytest.mark.parametrize('providers', [('qwen', 'qwen'), ('deepseek', 'deepseek'), ('qwen', 'deepseek')])
def test_atomic_concurrent_reservations(concurrency_database, settings, providers, scope):
    from threading import Barrier
    db_engine = concurrency_database
    Base.metadata.create_all(db_engine)
    with Session(db_engine) as db:
        user = User(email='race@example.org', password_hash='unused')
        db.add(user)
        db.commit()
        user_id = user.id
        second_user = User(email='second-race@example.org', password_hash='unused')
        db.add(second_user)
        db.commit()
        second_id = second_user.id
        access.set_access(db, user_id, authorized=True)
        access.set_access(db, second_id, authorized=True)
        user_ids = [user_id, second_id] if scope == 'global' else [user_id, user_id]
    settings.free_ai_max_concurrent_requests = 10
    settings.free_ai_monthly_credits = max(included.credits(included.cost(1028, 4096,
        included.route(name).price), settings.free_ai_credits_per_usd, 1) for name in providers)
    if scope == 'global':
        from decimal import Decimal
        maximum_cost = max(included.cost(1028, 4096, included.route(name).price) for name in providers)
        settings.free_ai_global_monthly_budget_usd = str(Decimal(maximum_cost) / 1000000)
        settings.free_ai_monthly_credits = 100000
    barrier = Barrier(2)
    def attempt(args):
        name, account_id = args
        with Session(db_engine) as db:
            barrier.wait(timeout=10)
            try:
                return included.reserve(db, account_id, included.route(name), 'JSON')
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, zip(providers, user_ids)))
    assert outcomes.count(429 if scope == 'user' else 503) == 1
    with Session(db_engine) as db:
        rows = list(db.scalars(select(AiUsage)))
        assert len(rows) == 1
        assert sum(map(included.ledger_credits, rows)) <= settings.free_ai_monthly_credits
    db_engine.dispose()


def test_concurrent_limit_and_expired_worker(client, settings, monkeypatch):
    _, _, user_id = account(client)
    with Session(engine) as db:
        first = included.reserve(db, user_id, included.route('qwen'), 'JSON')
        with pytest.raises(HTTPException) as error:
            included.reserve(db, user_id, included.route('deepseek'), 'JSON')
        assert error.value.status_code == 429
        item = db.get(AiUsage, first)
        item.created_at = included.now_utc().replace(year=2020)
        db.commit()
        second = included.reserve(db, user_id, included.route('deepseek'), 'JSON')
        assert db.get(AiUsage, first).status == 'expired'
        assert db.get(AiUsage, first).actual_credits == 0
        assert db.get(AiUsage, first).actual_cost_microusd > 0
        included.reconcile(db, second, useful=False)


@pytest.mark.parametrize('status', [400, 401, 403, 502, 503])
def test_fallback_only_temporary_and_no_double_charge(client, settings, monkeypatch, status):
    headers, project, _ = account(client)
    settings.free_ai_deepseek_fallback_to_qwen = True
    settings.free_ai_minute_request_limit = 1
    seen = []
    class Failed(Stub):
        async def generate(self, *args):
            raise ProviderError('private upstream detail', status,
                                usage={'input_tokens': 10, 'output_tokens': 0})
    def adapter(plan):
        seen.append(plan.provider)
        return Failed() if plan.provider == 'deepseek' else Stub()
    monkeypatch.setattr(included, 'adapter', adapter)
    response = client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body('code'))
    assert seen == (['deepseek', 'qwen'] if status == 503 else ['deepseek'])
    assert response.status_code == (201 if status == 503 else 502)
    assert 'private upstream detail' not in response.text
    assert client.get('/api/ai/included').json()['monthly_credits_used'] == (20 if status == 503 else 0)
    with Session(engine) as db:
        rows = list(db.scalars(select(AiUsage)))
        assert len({r.request_id for r in rows}) == 1
        assert rows[0].actual_credits == 0
        assert rows[0].actual_cost_microusd == 30


def test_stream_cancellation_and_failure_release_credits(client, settings, monkeypatch):
    _, _, user_id = account(client)
    class Interrupted(Stub):
        async def stream(self, *args):
            yield ProviderChunk(text='partial')
            raise ProviderError('internal', 503)
    monkeypatch.setattr(included, 'adapter', lambda plan: Interrupted())
    async def run():
        with Session(engine) as db:
            with pytest.raises(HTTPException):
                async for _ in included.run(db, user_id, 'qwen', 'JSON', lambda *args: None):
                    pass
            assert included.summary(db, user_id)['monthly_credits_used'] == 0
            row = db.scalar(select(AiUsage))
            assert row.actual_cost_microusd == row.reserved_cost_microusd
        monkeypatch.setattr(included, 'adapter', lambda plan: Stub())
        with Session(engine) as db:
            generator = included.run(db, user_id, 'deepseek', 'JSON', lambda *args: None)
            await anext(generator)
            await generator.aclose()
            assert included.summary(db, user_id)['monthly_credits_used'] == 0
            assert not list(db.scalars(select(AiUsage).where(AiUsage.status == 'reserved')))
    asyncio.run(run())


def test_invalid_structured_output_releases_user_credits(client, settings, monkeypatch):
    headers, project, _ = account(client)
    monkeypatch.setattr(included, 'adapter', lambda plan: Stub(text='invalid JSON'))
    response = client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body())
    assert response.status_code == 502
    assert client.get('/api/ai/included').json()['monthly_credits_used'] == 0
    with Session(engine) as db:
        assert db.scalar(select(AiUsage)).actual_cost_microusd == 200


def test_byok_independent_credentials_budget_and_credits(client, settings, monkeypatch):
    from educrea_api.services.ai import pricing
    from educrea_api.services.ai.providers import registry
    headers, project, _ = account(client)
    monkeypatch.setattr(included, 'adapter', lambda plan: Stub())
    assert client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body()).status_code == 201
    before = client.get('/api/ai/included').json()['monthly_credits_used']
    assert client.put('/api/ai/providers/deepseek/key', headers=headers,
                      json={'api_key': 'personal-deepseek-test'}).status_code == 204
    seen_keys = []
    class Personal(Stub):
        async def generate(self, key, *args):
            seen_keys.append(key)
            return await super().generate(key, *args)
    monkeypatch.setattr(registry, 'adapter', lambda name: Personal())
    monkeypatch.setattr(pricing, 'get_settings', lambda: Settings(paid_models_json=json.dumps({
        'deepseek': {'personal-model': {'input': 1000000, 'output': 2000000}}})))
    body = {**request_body(), 'provider': 'deepseek', 'model': 'personal-model', 'mode': 'paid'}
    estimate = client.post(f'/api/projects/{project}/ai/estimate', headers=headers, json=body).json()
    client.put('/api/ai/budget', headers=headers, json={'monthly_limit_microusd': 1000000})
    settings.free_ai_enabled = False
    response = client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json={**body,
        'paid_authorized': True, 'approved_max_cost_microusd': estimate['maximum_cost_microusd'],
        'approved_estimate_fingerprint': estimate['fingerprint']})
    assert response.status_code == 201, response.text
    assert seen_keys == ['personal-deepseek-test']
    assert client.get('/api/ai/included').json()['monthly_credits_used'] == before
    assert client.get('/api/ai/budget').json()['spent_or_reserved_microusd'] == 200


def test_teacher_shortcuts_and_section_stream_share_same_service(client, settings, monkeypatch):
    headers, project, _ = account(client)
    brief = {'title': 'Fracciones', 'kind': 'actividad', 'language': 'es', 'level': 'primaria',
             'instructions': 'Explica las fracciones', 'activity_type': 'cuestionario'}
    response = client.post(f'/api/projects/{project}/files', headers=headers,
                          json={'path': 'activity.json', 'content': json.dumps(brief)})
    assert response.status_code == 201, response.text
    seen = []
    def choose(plan):
        seen.append(plan.provider)
        return Stub(text=json.dumps({'summary': 'Actividad', 'changes': [
            {'path': 'index.html', 'content': '<h1>Fracciones</h1>'}]}))
    monkeypatch.setattr(included, 'adapter', choose)
    response = client.post(f'/api/projects/{project}/ai/from-brief', headers=headers, json={})
    assert response.status_code == 201, response.text
    assert seen == ['deepseek']
    assert response.json()['provider'] == 'educrea'
    files = client.get(f'/api/projects/{project}/files').json()
    current = next(f for f in files if f['path'] == 'activity.json')
    brief['kind'] = 'situacion'
    assert client.put(f'/api/projects/{project}/files/{current["id"]}', headers=headers,
        json={'content': json.dumps(brief), 'expected_version': current['version']}).status_code == 200
    section = 'Una propuesta didáctica para explicar las fracciones con ejemplos y materiales de aula.'
    monkeypatch.setattr(included, 'adapter', lambda plan: seen.append(plan.provider) or Stub(text=json.dumps({
        'summary': 'Sección', 'changes': [{'path': 'seccion.md', 'content': section}]})))
    response = client.post(f'/api/projects/{project}/ai/sections/stream', headers=headers,
                          json={'sections': ['Evaluación'], 'provider': 'educrea'})
    assert 'event: proposal' in response.text, response.text
    assert seen[-1] == 'qwen'
    assert 'qwen' not in response.text and 'deepseek' not in response.text
    assert client.get('/api/ai/included').json()['monthly_credits_used'] == 80


def test_institutional_adapter_limits_and_secret_repr(settings):
    for name in ('qwen', 'deepseek'):
        plan = included.route(name)
        adapter = included.adapter(plan)
        payload = adapter._payload(plan.model, 'Produce JSON', True)
        assert payload['max_tokens'] == settings.free_ai_max_output_tokens
        assert payload['stream_options']['include_usage'] is True
        assert plan.key not in repr(plan)
        assert adapter.url.startswith('https://')
    assert included.adapter(included.route('qwen')).extra_payload['enable_thinking'] is False
    assert included.adapter(included.route('deepseek')).extra_payload['thinking']['type'] == 'disabled'


def test_migration_upgrade_downgrade_preserves_byok(tmp_path, monkeypatch):
    from alembic.config import Config
    from alembic import command
    from educrea_api import config
    from sqlalchemy import inspect, MetaData, Table
    url = 'sqlite:///' + str(tmp_path / 'migrations.db')
    monkeypatch.setattr(config, 'get_settings', lambda: Settings(database_url=url))
    cfg = Config('alembic.ini')
    command.upgrade(cfg, '0012_project_assets')
    migration_engine = create_engine(url)
    metadata = MetaData()
    users = Table('users', metadata, autoload_with=migration_engine)
    usage = Table('ai_usage', metadata, autoload_with=migration_engine)
    user_id, usage_id = uuid4().hex, uuid4().hex
    with migration_engine.begin() as connection:
        connection.execute(users.insert().values(id=user_id, email='legacy@example.org', password_hash='unused',
                                                 created_at=included.now_utc()))
        connection.execute(usage.insert().values(id=usage_id, user_id=user_id, provider='deepseek', model='legacy',
            reserved_tokens=100, status='completed', mode='paid', created_at=included.now_utc()))
    command.upgrade(cfg, 'head')
    assert 'reserved_credits' in {col['name'] for col in inspect(migration_engine).get_columns('ai_usage')}
    command.downgrade(cfg, '0012_project_assets')
    assert 'reserved_credits' not in {col['name'] for col in inspect(migration_engine).get_columns('ai_usage')}
    with migration_engine.connect() as connection:
        row = connection.execute(usage.select()).one()
        assert row.id == usage_id and row.provider == 'deepseek' and row.mode == 'paid'
    command.upgrade(cfg, 'head')
    migration_engine.dispose()


def test_success_without_usage_keeps_ceiling_and_overrun_blocks_global_spend(client, settings, monkeypatch):
    headers, project, _ = account(client)
    monkeypatch.setattr(included, 'adapter', lambda plan: Stub(usage={}))
    response = client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body())
    assert response.status_code == 201
    with Session(engine) as db:
        row = db.scalar(select(AiUsage))
        assert row.actual_credits == row.reserved_credits
        assert row.actual_cost_microusd == row.reserved_cost_microusd
    settings.free_ai_global_monthly_budget_usd = '1'
    monkeypatch.setattr(included, 'adapter', lambda plan: Stub(usage={'input_tokens': 2000000, 'output_tokens': 0}))
    response = client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body())
    assert response.status_code == 201
    assert client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body()).status_code == 503
    with Session(engine) as db:
        rows = list(db.scalars(select(AiUsage)))
        assert all(row.actual_credits <= row.reserved_credits for row in rows)
        assert included.metrics(db)['estimated_cost_microusd'] > 1000000


def test_adapter_retains_reported_usage_on_provider_error():
    import httpx
    from educrea_api.services.ai.providers.compatible import CompatibleProvider
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503,
                json={'message': 'never expose this upstream body',
                      'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}))) as client:
            adapter = CompatibleProvider('deepseek', client)
            for streaming in (False, True):
                with pytest.raises(ProviderError) as error:
                    if streaming:
                        async for _ in adapter.stream('test-key', 'test-model', 'JSON'):
                            pass
                    else:
                        await adapter.generate('test-key', 'test-model', 'JSON')
                assert error.value.usage == {'input_tokens': 10, 'output_tokens': 5}
                assert 'never expose' not in str(error.value)
    asyncio.run(run())
