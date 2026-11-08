import copy
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from educrea_api.config import Settings
from educrea_api.db import Base
from educrea_api.models import TestTopup as Topup, TestWalletEntry as Entry, User
from educrea_api.services import billing
from conftest import engine
from test_auth_projects import register


@pytest.fixture
def configured(monkeypatch):
    settings = Settings(stripe_test_enabled=True, stripe_secret_key=SecretStr('sk_test_dummy'),
                        stripe_webhook_secret=SecretStr('whsec_dummy'), public_base_url='https://school.example.org')
    monkeypatch.setattr(billing, 'get_settings', lambda: settings)
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, request=httpx.Request('POST', url),
                              json={'id': 'cs_test_example', 'livemode': False,
                                    'url': 'https://checkout.stripe.com/c/pay/cs_test_example'})
    monkeypatch.setattr(billing.httpx, 'post', post)
    return settings, calls


def start(client):
    csrf = register(client, 'teacher@example.org')
    request_id = str(uuid4())
    response = client.post('/api/billing/checkout', json={'request_id': request_id}, headers={'X-CSRF-Token': csrf})
    assert response.status_code == 200, response.text
    return csrf, request_id, response.json()['topup_id']


def event(topup_id, **overrides):
    obj = {'id': 'cs_test_example', 'livemode': False, 'mode': 'payment', 'status': 'complete',
           'payment_status': 'paid', 'currency': 'eur', 'amount_total': 1000,
           'client_reference_id': topup_id,
           'metadata': {'educrea_topup_id': topup_id, 'educrea_scope': 'wallet_test_v1'}}
    obj.update(overrides)
    return {'id': 'evt_dummy', 'livemode': False, 'type': 'checkout.session.completed', 'data': {'object': obj}}


def deliver(client, body, timestamp=None, secret='whsec_dummy'):
    payload = json.dumps(body).encode()
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    signature = hmac.new(secret.encode(), timestamp.encode() + b'.' + payload, hashlib.sha256).hexdigest()
    return client.post('/api/billing/webhook', content=payload,
                       headers={'Stripe-Signature': f't={timestamp},v1={signature}'})


def test_checkout_fixed_amount_and_retries(client, configured):
    csrf, request_id, _ = start(client)
    calls = configured[1]
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == 'https://api.stripe.com/v1/checkout/sessions'
    assert kwargs['data']['mode'] == 'payment'
    assert 'payment_method_types[0]' not in kwargs['data']
    assert kwargs['data']['line_items[0][price_data][unit_amount]'] == '1000'
    assert kwargs['data']['success_url'] == 'https://school.example.org/saldo?checkout=returned'
    assert client.post('/api/billing/checkout', json={'request_id': request_id},
                       headers={'X-CSRF-Token': csrf}).status_code == 200
    assert len(calls) == 1
    assert client.get('/api/billing/wallet?checkout=returned').json()['balance_microeur'] == 0
    assert client.post('/api/billing/checkout', json={'request_id': request_id, 'amount': 1},
                       headers={'X-CSRF-Token': csrf}).status_code == 422


def test_paid_only_once_across_events_and_out_of_order_delivery(client, configured):
    _, _, topup_id = start(client)
    pending = event(topup_id, payment_status='unpaid')
    assert deliver(client, pending).status_code == 200
    assert client.get('/api/billing/wallet').json()['balance_microeur'] == 0
    paid = event(topup_id)
    assert deliver(client, paid).status_code == 200
    assert deliver(client, paid).status_code == 200
    paid['type'] = 'checkout.session.async_payment_succeeded'
    paid['id'] = 'evt_other'
    assert deliver(client, paid).status_code == 200
    for kind in ['checkout.session.expired', 'checkout.session.async_payment_failed']:
        paid['type'] = kind
        assert deliver(client, paid).status_code == 200
    wallet = client.get('/api/billing/wallet')
    assert wallet.headers['cache-control'] == 'no-store'
    assert wallet.json()['balance_microeur'] == 10_000_000
    assert len(wallet.json()['entries']) == 1
    assert wallet.json()['topups'][0]['state'] == 'paid'


@pytest.mark.parametrize('changes', [dict(livemode=True), dict(amount_total=999), dict(amount_total='1000'),
    dict(currency='usd'), dict(client_reference_id=str(uuid4())), dict(id='cs_test_another'),
    dict(mode='subscription'), dict(id='cs_live_example')])
def test_payment_must_match_local_order(client, configured, changes):
    _, _, topup_id = start(client)
    assert deliver(client, event(topup_id, **changes)).status_code == 400
    assert client.get('/api/billing/wallet').json()['balance_microeur'] == 0


def test_webhook_signatures_and_mode(client, configured):
    _, _, topup_id = start(client)
    body = event(topup_id)
    assert deliver(client, body, secret='wrong').status_code == 400
    assert deliver(client, body, timestamp=int(time.time()) - 301).status_code == 400
    assert deliver(client, body, timestamp=int(time.time()) + 301).status_code == 400
    assert client.post('/api/billing/webhook', json=body).status_code == 400
    assert client.post('/api/billing/webhook', content=b'x' * 262145).status_code == 413
    body['livemode'] = True
    assert deliver(client, body).status_code == 400
    assert client.get('/api/billing/wallet').json()['balance_microeur'] == 0


def test_sessions_csrf_guests_and_account_isolation(client, configured):
    assert client.get('/api/billing/wallet').status_code == 401
    client.post('/api/auth/guest')
    assert client.get('/api/billing/wallet').status_code == 403
    client.cookies.clear()
    csrf, _, topup_id = start(client)
    assert client.post('/api/billing/checkout', json={'request_id': str(uuid4())}).status_code == 403
    assert deliver(client, event(topup_id)).status_code == 200  # Signature replaces CSRF on webhook only.
    client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf})
    register(client, 'other@example.org')
    assert client.get('/api/billing/wallet').json()['balance_microeur'] == 0
    assert client.get('/api/billing/wallet').json()['entries'] == []
    assert client.get('/api/billing/wallet').json()['topups'] == []


def test_disabled_or_live_key_never_calls_stripe(client, configured):
    settings, calls = configured
    csrf = register(client, 'teacher@example.org')
    for key, enabled in [('sk_live_dummy', True), ('sk_test_dummy', False), ('', True)]:
        settings.stripe_secret_key = SecretStr(key)
        settings.stripe_test_enabled = enabled
        assert client.post('/api/billing/checkout', json={'request_id': str(uuid4())},
                           headers={'X-CSRF-Token': csrf}).status_code == 503
        assert client.get('/api/billing/wallet').json()['enabled'] is False
    assert calls == []


@pytest.mark.parametrize('mutation', ['malformed', 'foreign_product', 'unknown_event', 'expired', 'failed'])
def test_nonpaying_events_never_credit(client, configured, mutation):
    _, _, topup_id = start(client)
    body = event(topup_id)
    expected = 200
    if mutation == 'malformed':
        body['data'] = None
        expected = 400
    elif mutation == 'foreign_product':
        body['data']['object']['metadata']['educrea_scope'] = 'another_product'
    elif mutation == 'unknown_event':
        body['type'] = 'payment_intent.succeeded'
    elif mutation == 'expired':
        body['type'] = 'checkout.session.expired'
    else:
        body['type'] = 'checkout.session.async_payment_failed'
    assert deliver(client, body).status_code == expected
    assert client.get('/api/billing/wallet').json()['balance_microeur'] == 0


def test_timeout_reuses_persisted_idempotency_key(client, configured, monkeypatch):
    calls = []
    real_post = billing.httpx.post
    def timeout(url, **kwargs):
        calls.append(kwargs['headers']['Idempotency-Key'])
        raise httpx.ReadTimeout('redacted')
    monkeypatch.setattr(billing.httpx, 'post', timeout)
    csrf = register(client, 'teacher@example.org')
    request_id = str(uuid4())
    for _ in range(2):
        assert client.post('/api/billing/checkout', json={'request_id': request_id},
                           headers={'X-CSRF-Token': csrf}).status_code == 502
    assert calls[0] == calls[1]
    monkeypatch.setattr(billing.httpx, 'post', real_post)
    assert client.post('/api/billing/checkout', json={'request_id': request_id},
                       headers={'X-CSRF-Token': csrf}).status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Topup)) == 1


def test_concurrent_deliveries_credit_once(tmp_path):
    concurrent_engine = create_engine('sqlite:///' + str(tmp_path / 'concurrent.db'), connect_args={'timeout': 15})
    Base.metadata.create_all(concurrent_engine)
    with Session(concurrent_engine) as db:
        user = User(email='teacher@example.org', password_hash='unused')
        db.add(user); db.flush()
        topup = Topup(user_id=user.id, request_id=uuid4(), return_base='https://school.example.org',
                      session_id='cs_test_example', state='pending')
        db.add(topup); db.commit()
        body = event(str(topup.id))
    def run(_):
        with Session(concurrent_engine) as db:
            billing.fulfill(db, copy.deepcopy(body))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run, range(8)))
    with Session(concurrent_engine) as db:
        assert db.scalar(select(func.sum(Entry.amount_microeur))) == 10_000_000
    concurrent_engine.dispose()


def test_migration_reversible(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from educrea_api.config import get_settings
    monkeypatch.setattr(get_settings(), 'database_url', 'sqlite:///' + str(tmp_path / 'migration.db'))
    cfg = Config('alembic.ini')
    command.upgrade(cfg, '0019_project_audios')
    command.upgrade(cfg, 'head')
    migration_engine = create_engine(get_settings().database_url)
    assert 'billing_test_entries' in inspect(migration_engine).get_table_names()
    command.downgrade(cfg, '0019_project_audios')
    assert 'billing_test_entries' not in inspect(migration_engine).get_table_names()
    assert 'users' in inspect(migration_engine).get_table_names()
    command.upgrade(cfg, 'head')
    migration_engine.dispose()
