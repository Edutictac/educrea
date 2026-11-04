from functools import lru_cache
import os
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://edustudio:edustudio@localhost:5432/edustudio"
    cookie_secure: bool = True
    session_days: int = 7
    credential_keys: SecretStr | None = None
    gemini_free_models: str = ""
    openrouter_free_models: str = ""
    groq_free_models: str = ""
    ollama_free_models: str = ""
    ollama_base_url: str = ""
    paid_models_json: str = "{}"
    # Single sign-on (OpenID Connect, e.g. Authentik at id.edutictac.es). Disabled until issuer and client are set.
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: SecretStr | None = None
    oidc_redirect_uri: str = ""
    oidc_scopes: str = "openid email profile"
    oidc_link_by_email: bool = True
    local_auth_enabled: bool = True
    allow_insecure_urls: bool = False  # only for local development with http:// sources
    mcp_servers_json: str = "{}"
    ai_max_user_budget_microusd: int = 20000000
    ai_daily_personal_requests: int = 200  # loop guard for personal-key providers; the provider sets the real quota
    ai_daily_user_requests: int = 20
    ai_daily_installation_requests: int = 200
    ai_daily_user_tokens: int = 400000
    ai_daily_installation_tokens: int = 4000000
    model_config = SettingsConfigDict(env_prefix="EDUSTUDIO_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    overrides: dict[str, str] = {}
    database_url_file = os.environ.get("EDUSTUDIO_DATABASE_URL_FILE")
    if database_url_file:
        overrides["database_url"] = Path(database_url_file).read_text().strip()
    credential_keys_file = os.environ.get("EDUSTUDIO_CREDENTIAL_KEYS_FILE")
    if credential_keys_file:
        overrides["credential_keys"] = Path(credential_keys_file).read_text().strip()
    oidc_secret_file = os.environ.get("EDUSTUDIO_OIDC_CLIENT_SECRET_FILE")
    if oidc_secret_file:
        overrides["oidc_client_secret"] = Path(oidc_secret_file).read_text().strip()
    return Settings(**overrides)

