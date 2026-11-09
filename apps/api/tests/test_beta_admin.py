import json
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from conftest import engine
from educrea_api import db as db_module
from educrea_api.config import get_settings
from educrea_api.models import User, BetaInvitation, BetaAdminAudit, IncludedAiAccess
from educrea_api.services import beta_admin, beta_mail, beta_invitations
from educrea_api.services.ai import access, included
from test_auth_projects import register
from test_oidc import sso, login_as, start, claims_for_next


@pytest.fixture
def admin(client):
    csrf = register(client, 'owner@example.org')
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == 'owner@example.org'))
        user.is_admin = True
        user_id = user.id
        db.commit()
    return {'X-CSRF-Token': csrf}, user_id


@pytest.fixture
def mail(monkeypatch):
    s = get_settings()
    for name, value in {'smtp_host': 'smtp.example.org', 'smtp_from': 'beta@example.org',
        'public_base_url': 'https://educrea.example.org', 'oidc_issuer': 'https://id.example.org',
        'oidc_client_id': 'test-client', 'smtp_username': 'mail-user',
        'smtp_password': SecretStr('test-only-smtp-password')}.items():
        monkeypatch.setattr(s, name, value)
    sent = []
    monkeypatch.setattr(beta_mail, 'send_invitation', lambda email, days: sent.append(email))
    return sent


def test_normal_accounts_cannot_enter_admin_or_self_assign(client):
    assert client.get('/api/admin/beta').status_code == 401
    result = client.post('/api/auth/register', json={'email': 'self@example.org', 'password': 'a-long-test-password', 'is_admin': True})
    assert result.json()['user']['is_admin'] is False
    csrf = result.json()['csrf_token']
    assert client.get('/api/admin/beta').status_code == 403
    for path, body in [(f'/api/admin/beta/users/{uuid4()}/access', {'authorized': True}),
                        ('/api/admin/beta/invitations', {'email': 'teacher@example.org'})]:
        method = client.put if 'users/' in path else client.post
        assert method(path, headers={'X-CSRF-Token': csrf}, json=body).status_code == 403
    assert client.post('/api/admin/beta/role', json={'is_admin': True}).status_code == 404


def test_admin_dashboard_grants_and_revokes_with_csrf_and_audit(client, admin):
    headers, actor_id = admin
    with Session(engine) as db:
        teacher = User(email='teacher@example.org', password_hash='unused')
        db.add(teacher)
        db.commit()
        target_id = teacher.id
        access.join_waitlist(db, target_id, 'Música en Primaria', 'Crear actividades educativas.')
    response = client.get('/api/admin/beta')
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert response.json()['waitlist'][0]['email'] == 'teacher@example.org'
    route = f'/api/admin/beta/users/{target_id}/access'
    assert client.put(route, json={'authorized': True}).status_code == 403
    for authorized in [True, False, True]:
        assert client.put(route, headers=headers, json={'authorized': authorized}).status_code == 200
    with Session(engine) as db:
        assert access.status(db, target_id) == 'invited'
        assert db.get(User, target_id).is_admin is False
        audits = list(db.scalars(select(BetaAdminAudit)))
        assert len(audits) == 3 and all(item.actor_id == actor_id for item in audits)


def test_missing_mail_config_does_not_create_invitation(client, admin):
    headers, _ = admin
    assert client.get('/api/admin/beta').json()['mail_ready'] is False
    response = client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'teacher@example.org'})
    assert response.status_code == 503
    with Session(engine) as db:
        assert db.scalar(select(BetaInvitation)) is None


def test_send_records_delivery_without_granting_access_or_admin(client, admin, mail):
    headers, actor = admin
    assert client.post('/api/admin/beta/invitations', json={'email': 'teacher@example.org'}).status_code == 403
    response = client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'Teacher@example.org'})
    assert response.status_code == 200 and response.json()['state'] == 'sent'
    assert mail == ['teacher@example.org']
    assert 'password' not in response.text and 'token' not in response.text
    with Session(engine) as db:
        assert db.scalar(select(IncludedAiAccess)) is None
        assert db.scalar(select(BetaAdminAudit)).actor_id == actor
    assert client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'teacher@example.org'}).status_code == 429


def test_failure_is_safe_and_does_not_authorize(client, admin, mail, monkeypatch):
    headers, _ = admin
    def fail(*args):
        raise HTTPException(503, 'test-only-smtp-password')
    monkeypatch.setattr(beta_mail, 'send_invitation', fail)
    response = client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'teacher@example.org'})
    assert response.status_code == 503 and 'test-only-smtp-password' not in response.text
    with Session(engine) as db:
        assert db.scalar(select(BetaInvitation)).state == 'failed'
        assert db.scalar(select(IncludedAiAccess)) is None
        assert db.scalar(select(BetaAdminAudit)).action == 'invitation_failed'


def test_daily_limit_counts_failed_attempts(client, admin, mail, monkeypatch):
    monkeypatch.setattr(get_settings(), 'beta_invitation_daily_limit', 1)
    headers, _ = admin
    assert client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'one@example.org'}).status_code == 200
    assert client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'two@example.org'}).status_code == 429
    assert mail == ['one@example.org']


def test_revoked_invitation_cannot_be_used_and_access_revocation_cancels_email_invite(client, admin, mail):
    headers, actor = admin
    response = client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'teacher@example.org'})
    invite_id = UUID(response.json()['id'])
    with Session(engine) as db:
        teacher = User(email='teacher@example.org', password_hash='unused')
        db.add(teacher); db.commit()
        target = teacher.id
        access.set_access(db, target, authorized=False, actor_id=actor)
        assert db.get(BetaInvitation, invite_id).state == 'revoked'
        beta_invitations.claim_verified(db, target, 'teacher@example.org')
        assert access.status(db, target) == 'revoked'
    assert client.post(f'/api/admin/beta/invitations/{invite_id}/revoke', headers=headers).status_code == 200


def test_email_headers_and_privileges_cannot_be_injected(client, admin, mail):
    headers, _ = admin
    for data in [{'email': 'a@example.org\nBcc: other@example.org'},
                 {'email': 'a@example.org', 'is_admin': True}, {'email': 'a@example.org', 'actor_id': str(uuid4())}]:
        assert client.post('/api/admin/beta/invitations', headers=headers, json=data).status_code == 422
    assert mail == []


def test_verified_sso_claims_only_matching_live_invitation(client, admin, mail, sso):
    headers, _ = admin
    invited = client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'teacher@example.org'}).json()
    client.post('/api/auth/logout', headers=headers)
    # A matching local registration cannot redeem an invitation without proof of mailbox ownership.
    csrf = register(client, 'teacher@example.org')
    assert client.get('/api/ai/included').json()['authorized'] is False
    client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf})
    assert login_as(client, sub='teacher', email='teacher@example.org', is_admin=True).status_code == 303
    user = client.get('/api/auth/me').json()['user']
    assert user['included_ai_authorized'] is True and user['is_admin'] is False
    with Session(engine) as db:
        assert db.get(BetaInvitation, UUID(invited['id'])).state == 'accepted'
        assert len(list(db.scalars(select(BetaAdminAudit).where(BetaAdminAudit.action == 'invitation_accepted')))) == 1
    client.cookies.clear()
    assert login_as(client, sub='teacher', email='teacher@example.org').status_code == 303
    with Session(engine) as db:
        assert len(list(db.scalars(select(BetaAdminAudit).where(BetaAdminAudit.action == 'invitation_accepted')))) == 1


@pytest.mark.parametrize('state,expired', [('revoked', False), ('failed', False), ('sent', True)])
def test_expired_or_unsent_invitations_never_grant_access(client, admin, mail, sso, state, expired):
    headers, _ = admin
    result = client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'teacher@example.org'}).json()
    with Session(engine) as db:
        item = db.get(BetaInvitation, UUID(result['id']))
        item.state = state
        if expired: item.expires_at = included.now_utc() - timedelta(seconds=1)
        db.commit()
    client.cookies.clear()
    assert login_as(client, sub='teacher', email='teacher@example.org').status_code == 303
    assert client.get('/api/auth/me').json()['user']['included_ai_authorized'] is False


def test_admin_role_can_only_be_bootstrapped_from_server(client, monkeypatch, capsys):
    csrf = register(client, 'operator@example.org')
    monkeypatch.setattr(db_module, 'SessionLocal', lambda: Session(engine))
    beta_admin.main(['grant', '--email', 'operator@example.org'])
    assert json.loads(capsys.readouterr().out)['is_admin'] is True
    assert client.get('/api/admin/beta').status_code == 200
    beta_admin.main(['revoke', '--email', 'operator@example.org'])
    capsys.readouterr()
    assert client.get('/api/admin/beta').status_code == 403


def test_smtp_uses_verified_tls_and_never_embeds_secrets(monkeypatch, mail):
    # Restore the real sender to exercise SMTP framing without any network connection.
    from importlib import reload
    reload(beta_mail)
    seen = []
    class SMTP:
        def __init__(self, host, port, **kwargs): seen.append(('connect', host, port))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self, *, context): assert context.check_hostname
        def login(self, user, password): assert password == 'test-only-smtp-password'
        def send_message(self, message):
            text = str(message)
            assert 'test-only-smtp-password' not in text and 'Bearer' not in text
            assert 'https://educrea.example.org/login' in text
            assert message['To'] == 'teacher@example.org'
            return {}
    monkeypatch.setattr(beta_mail.smtplib, 'SMTP', SMTP)
    beta_mail.send_invitation('teacher@example.org', 7)
    assert seen


def test_admin_migration_is_reversible_and_does_not_auto_grant(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, MetaData, Table, inspect
    from educrea_api import config
    from educrea_api.config import Settings
    url = 'sqlite:///' + str(tmp_path / 'admin-migration.db')
    monkeypatch.setattr(config, 'get_settings', lambda: Settings(database_url=url))
    cfg = Config('alembic.ini')
    command.upgrade(cfg, '0015_included_ai_waitlist')
    migration_engine = create_engine(url)
    users = Table('users', MetaData(), autoload_with=migration_engine)
    identifier = uuid4().hex
    with migration_engine.begin() as conn:
        conn.execute(users.insert().values(id=identifier, email='existing@example.org', password_hash='unused',
                                          created_at=included.now_utc()))
    command.upgrade(cfg, 'head')
    updated = Table('users', MetaData(), autoload_with=migration_engine)
    with migration_engine.connect() as conn:
        assert conn.scalar(select(updated.c.is_admin)) is False
    command.downgrade(cfg, '0015_included_ai_waitlist')
    assert 'beta_invitations' not in inspect(migration_engine).get_table_names()
    assert 'is_admin' not in {c['name'] for c in inspect(migration_engine).get_columns('users')}
    with migration_engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(users)) == 1
    command.upgrade(cfg, 'head')
    migration_engine.dispose()


def test_missing_verified_claim_does_not_redeem_invitation(client, admin, mail, sso):
    headers, _ = admin
    client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'teacher@example.org'})
    client.cookies.clear()
    query, _ = start(client)
    claims_for_next.update({'sub': 'teacher', 'email': 'teacher@example.org', 'nonce': query['nonce'][0]})
    result = client.get('/api/auth/oidc/callback', params={'code': 'ok', 'state': query['state'][0]}, follow_redirects=False)
    assert result.status_code == 403
    with Session(engine) as db:
        assert db.scalar(select(IncludedAiAccess)) is None


def test_revoked_admin_role_is_rechecked_inside_mutations(client, admin, mail):
    headers, actor = admin
    with Session(engine) as db:
        db.get(User, actor).is_admin = False
        db.commit()
    response = client.post('/api/admin/beta/invitations', headers=headers, json={'email': 'teacher@example.org'})
    assert response.status_code == 403 and mail == []


def test_admin_can_adjust_image_limits_with_csrf_validation_and_audit(client, admin):
    headers, actor = admin
    assert 'image_limits' in client.get('/api/admin/beta').json()
    assert client.put('/api/admin/beta/image-limits',
                      json={'weekly_limit': 5, 'global_daily_limit': 50}).status_code == 403
    response = client.put('/api/admin/beta/image-limits', headers=headers,
                          json={'weekly_limit': 5, 'global_daily_limit': 50})
    assert response.status_code == 200
    assert response.json()['weekly_limit'] == 5 and response.json()['global_daily_limit'] == 50
    limits = client.get('/api/admin/beta/image-limits').json()
    assert limits['weekly_custom'] == 5 and limits['global_daily_custom'] == 50
    assert client.get('/api/admin/beta').json()['image_limits']['weekly_limit'] == 5
    # Negative values and unknown fields must be rejected before persistence.
    for body in ({'weekly_limit': -1, 'global_daily_limit': 50},
                 {'weekly_limit': 5, 'global_daily_limit': -1},
                 {'weekly_limit': 5}):
        assert client.put('/api/admin/beta/image-limits', headers=headers, json=body).status_code == 422
    with Session(engine) as db:
        audit = db.scalar(select(BetaAdminAudit).where(BetaAdminAudit.action == 'image_limits_updated'))
        assert audit.actor_id == actor
        assert db.scalar(select(func.count()).select_from(BetaAdminAudit)) == 1


def test_admin_video_limits_require_role_csrf_and_are_audited(client, admin):
    headers, actor = admin
    path = '/api/admin/beta/video-limits'
    assert client.get(path).headers['cache-control'] == 'no-store'
    assert client.put(path, json={'daily_limit': 2, 'global_daily_limit': 10}).status_code == 403
    response = client.put(path, headers=headers, json={'daily_limit': 2, 'global_daily_limit': 10})
    assert response.status_code == 200
    assert response.json()['daily_custom'] == 2
    assert client.get('/api/admin/beta').json()['video_limits']['global_daily_limit'] == 10
    for body in ({'daily_limit': -1, 'global_daily_limit': 10},
                 {'daily_limit': 2, 'global_daily_limit': -1},
                 {'daily_limit': 2},
                 {'daily_limit': 2, 'global_daily_limit': 10, 'enabled': True}):
        assert client.put(path, headers=headers, json=body).status_code == 422
    with Session(engine) as db:
        audit = db.scalar(select(BetaAdminAudit).where(BetaAdminAudit.action == 'video_limits_updated'))
        assert audit.actor_id == actor
        db.get(User, actor).is_admin = False
        db.commit()
    assert client.get(path).status_code == 403
    assert client.put(path, headers=headers, json={'daily_limit': 0, 'global_daily_limit': 0}).status_code == 403
