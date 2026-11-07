"""Guest BYOK exists only for the lifetime of one HTTP request, including SSE streaming."""
from contextvars import ContextVar
import json

from pydantic import SecretStr
from starlette.responses import JSONResponse

_keys: ContextVar[dict] = ContextVar('guest_byok', default={})
PROVIDERS = frozenset({'gemini', 'mistral', 'openrouter', 'groq', 'openai', 'anthropic', 'deepseek'})
HEADER = b'x-educrea-temporary-keys'


def credential(db, user_id, provider):
    from ...models import User
    user = db.get(User, user_id)
    return _keys.get().get(provider) if user and user.is_guest else None


class TemporaryCredentialMiddleware:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        values = {}
        if scope['type'] == 'http':
            raw = next((v for k, v in scope.get('headers', []) if k.lower() == HEADER), None)
            if raw:
                try:
                    if len(raw) > 8192: raise ValueError()
                    data = json.loads(raw)
                    if not isinstance(data, dict) or len(data) > len(PROVIDERS): raise ValueError()
                    for provider, item in data.items():
                        if provider not in PROVIDERS or not isinstance(item, dict): raise ValueError()
                        key, confirmations = item.get('key'), item.get('confirmed', [])
                        if not isinstance(key, str) or not 10 <= len(key) <= 512: raise ValueError()
                        if (not isinstance(confirmations, list) or len(confirmations) > 30
                                or any(not isinstance(m, str) or len(m) > 100 for m in confirmations)): raise ValueError()
                        values[provider] = {'key': SecretStr(key), 'confirmed': confirmations}
                except (ValueError, TypeError, UnicodeError):
                    await JSONResponse({'detail': 'Credenciales temporales no válidas'}, status_code=422)(scope, receive, send)
                    return
        token = _keys.set(values)
        try:
            await self.app(scope, receive, send)
        finally:
            _keys.reset(token)
