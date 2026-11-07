import json
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from conftest import engine
from educrea_api import db as db_module
from educrea_api.models import AiUsage, AiCredential, IncludedAiAccess, IncludedAiWaitlist, User
from educrea_api.services.ai import access, included
from test_included_ai import account, settings, request_body
from test_auth_projects import register

REQUEST = {'teaching_context': 'Música en Primaria', 'intended_use': 'Crear actividades musicales accesibles para el aula.'}


def test_waitlist_requires_login_and_csrf(client):
    assert client.get('/api/ai/included/waitlist').status_code == 401
    assert client.post('/api/ai/included/waitlist', json=REQUEST).status_code == 401
    account(client, invited=False)
    assert client.post('/api/ai/included/waitlist', json=REQUEST).status_code == 403


def test_join_is_idempotent_and_never_grants_permission_or_spends(client, settings, monkeypatch):
    headers, project, user_id = account(client, invited=False)
    monkeypatch.setattr(included, 'adapter', lambda *args: pytest.fail('A waitlist request must never invoke AI'))
    assert client.get('/api/ai/included/waitlist').json() == {'status': 'none'}
    first = client.post('/api/ai/included/waitlist', headers=headers, json=REQUEST)
    assert first.status_code == 200 and first.json()['status'] == 'pending'
    second = client.post('/api/ai/included/waitlist', headers=headers, json=REQUEST)
    assert second.json()['requested_at'] == first.json()['requested_at']
    assert client.get('/api/ai/included').json()['authorized'] is False
    assert client.post(f'/api/projects/{project}/ai/proposals', headers=headers, json=request_body()).status_code == 403
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(IncludedAiWaitlist)) == 1
        assert db.get(IncludedAiAccess, user_id) is None
        assert db.scalar(select(AiUsage)) is None and db.scalar(select(AiCredential)) is None


@pytest.mark.parametrize('extra', [{'status': 'accepted'}, {'user_id': str(uuid4())}, {'authorized': True}])
def test_cannot_choose_approval_or_another_account(client, extra):
    headers, _, _ = account(client, invited=False)
    assert client.post('/api/ai/included/waitlist', headers=headers, json={**REQUEST, **extra}).status_code == 422
    with Session(engine) as db:
        assert db.scalar(select(IncludedAiWaitlist)) is None


@pytest.mark.parametrize('data', [
    {'teaching_context': '   ', 'intended_use': REQUEST['intended_use']},
    {'teaching_context': 'x' * 301, 'intended_use': REQUEST['intended_use']},
    {'teaching_context': REQUEST['teaching_context'], 'intended_use': 'short'},
    {'teaching_context': REQUEST['teaching_context'], 'intended_use': 'x' * 1001},
])
def test_validation_and_size_limits(client, data):
    headers, _, _ = account(client, invited=False)
    assert client.post('/api/ai/included/waitlist', headers=headers, json=data).status_code == 422


def test_requests_are_visible_only_to_their_owner(client):
    headers, _, _ = account(client, invited=False)
    client.post('/api/ai/included/waitlist', headers=headers, json=REQUEST)
    client.post('/api/auth/logout', headers=headers)
    csrf = register(client, 'other-waitlist@example.org')
    assert client.get('/api/ai/included/waitlist', params={'all': True}).json() == {'status': 'none'}
    response = client.post('/api/ai/included/waitlist', headers={'X-CSRF-Token': csrf},
                           json={**REQUEST, 'teaching_context': 'Inglés en Secundaria'})
    assert response.json()['teaching_context'] == 'Inglés en Secundaria'
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(IncludedAiWaitlist)) == 2


def test_manual_approval_revocation_and_rejoin(client, settings, monkeypatch, capsys):
    headers, _, user_id = account(client, invited=False)
    client.post('/api/ai/included/waitlist', headers=headers, json=REQUEST)
    monkeypatch.setattr(db_module, 'SessionLocal', lambda: Session(engine))
    access.main(['waitlist'])
    pending = json.loads(capsys.readouterr().out)
    assert len(pending) == 1 and pending[0]['user_id'] == str(user_id)
    access.main(['grant', '--user-id', str(user_id)])
    capsys.readouterr()
    assert client.get('/api/ai/included/waitlist').json()['status'] == 'accepted'
    assert client.get('/api/ai/included').json()['authorized'] is True
    assert client.post('/api/ai/included/waitlist', headers=headers, json=REQUEST).status_code == 409
    access.main(['waitlist'])
    assert json.loads(capsys.readouterr().out) == []
    access.main(['revoke', '--user-id', str(user_id)])
    capsys.readouterr()
    assert client.get('/api/ai/included/waitlist').json()['status'] == 'closed'
    assert client.get('/api/ai/included').json()['authorized'] is False
    assert client.post('/api/ai/included/waitlist', headers=headers, json=REQUEST).json()['status'] == 'pending'
    assert client.get('/api/ai/included').json()['authorized'] is False


def test_waitlist_migration_leaves_access_and_existing_accounts_unchanged(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, MetaData, Table
    from educrea_api import config
    from educrea_api.config import Settings
    url = 'sqlite:///' + str(tmp_path / 'waitlist-migration.db')
    monkeypatch.setattr(config, 'get_settings', lambda: Settings(database_url=url))
    cfg = Config('alembic.ini')
    command.upgrade(cfg, '0014_included_ai_access')
    migration_engine = create_engine(url)
    metadata = MetaData()
    users = Table('users', metadata, autoload_with=migration_engine)
    grants = Table('included_ai_access', metadata, autoload_with=migration_engine)
    user_id = uuid4().hex
    with migration_engine.begin() as conn:
        conn.execute(users.insert().values(id=user_id, email='existing-waitlist@example.org',
                                          password_hash='unused', created_at=included.now_utc()))
        conn.execute(grants.insert().values(user_id=user_id, granted_at=included.now_utc()))
    command.upgrade(cfg, 'head')
    with migration_engine.connect() as conn:
        waiting = Table('included_ai_waitlist', MetaData(), autoload_with=conn)
        assert conn.scalar(select(func.count()).select_from(waiting)) == 0
    command.downgrade(cfg, '0014_included_ai_access')
    assert 'included_ai_waitlist' not in inspect(migration_engine).get_table_names()
    with migration_engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(users)) == 1
        assert conn.scalar(select(func.count()).select_from(grants)) == 1
    command.upgrade(cfg, 'head')
    migration_engine.dispose()


from test_included_ai import concurrency_database


@pytest.mark.parametrize('operation', ['duplicate', 'approval'])
def test_waitlist_requests_serialize_with_each_other_and_manual_approval(concurrency_database, operation):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from educrea_api.db import Base
    Base.metadata.create_all(concurrency_database)
    with Session(concurrency_database) as db:
        user = User(email='waitlist-race@example.org', password_hash='unused')
        db.add(user)
        db.commit()
        user_id = user.id
    barrier = Barrier(2)
    def worker(index):
        from fastapi import HTTPException
        with Session(concurrency_database) as db:
            barrier.wait(timeout=10)
            try:
                if operation == 'approval' and index == 1:
                    return access.set_access(db, user_id, authorized=True)
                return access.join_waitlist(db, user_id, REQUEST['teaching_context'], REQUEST['intended_use'])
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [0, 1]))
    with Session(concurrency_database) as db:
        waiting = list(db.scalars(select(IncludedAiWaitlist)))
        if operation == 'duplicate':
            assert len(waiting) == 1 and waiting[0].status == 'pending'
            assert all(isinstance(item, dict) and item['status'] == 'pending' for item in results)
            assert access.status(db, user_id) == 'not_invited'
        else:
            assert access.status(db, user_id) == 'invited'
            assert not waiting or (len(waiting) == 1 and waiting[0].status == 'accepted')
