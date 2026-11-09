from functools import lru_cache
import os
from pathlib import Path

from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    @field_validator("free_ai_weekly_credits", mode="before")
    @classmethod
    def optional_weekly_credits(cls, value):
        return None if value == "" else value

    database_url: str = "postgresql+psycopg://educrea:educrea@localhost:5432/educrea"
    cookie_secure: bool = True
    session_days: int = 7
    credential_keys: SecretStr | None = None
    gemini_free_models: str = ""
    openrouter_free_models: str = ""
    groq_free_models: str = ""
    mistral_free_models: str = ""  # Deprecated: Mistral API requires billing; ignored by the free-model registry.
    ollama_free_models: str = ""
    ollama_base_url: str = ""
    paid_models_json: str = "{}"
    # BYOK image generation. Empty by default: only administrator-approved models and prices can spend money.
    image_models_json: str = "{}"
    ai_daily_image_requests: int = Field(default=20, gt=0)
    image_request_timeout_seconds: int = Field(default=120, ge=1, le=300)
    # Images with IA EduCrea for invited accounts: institutional Gemini key, a model of the image catalog, and
    # count-based limits (each image has a fixed price borne by EduCrea). Disabled by default.
    included_images_enabled: bool = False
    included_image_model: str = ""
    included_images_weekly_limit: int = Field(default=10, ge=0)
    included_images_global_daily_limit: int = Field(default=50, ge=0)
    # BYOK video generation. Admin-approved models and per-second prices; empty by default.
    video_models_json: str = "{}"
    ai_daily_video_requests: int = Field(default=10, gt=0)
    ai_daily_global_video_requests: int = Field(default=0, ge=0)
    video_request_timeout_seconds: int = Field(default=300, ge=30, le=600)
    # Included institutional AI. No personal credentials or implicit paid-model activation.
    free_ai_enabled: bool = False
    # Preferred institutional provider for every task; falls back to the task role when it is not configured.
    free_ai_primary_provider: str = "gemini"
    free_ai_monthly_credits: int = Field(default=10000, ge=0)
    free_ai_weekly_credits: int | None = Field(default=None, ge=0)
    free_ai_credits_per_usd: int = Field(default=100000, gt=0)
    free_ai_min_credits_per_request: int = Field(default=1, ge=0)
    free_ai_minute_request_limit: int = Field(default=15, gt=0)
    free_ai_hourly_request_limit: int = Field(default=30, gt=0)
    free_ai_daily_request_limit: int = Field(default=100, gt=0)
    # Installation-wide request cap shared by all users (0 disables it). Protects a single shared free-tier key.
    free_ai_global_daily_request_limit: int = Field(default=0, ge=0)
    free_ai_max_concurrent_requests: int = Field(default=1, gt=0)
    free_ai_max_input_tokens: int = Field(default=32768, gt=0)
    free_ai_max_context_tokens: int = Field(default=30000, gt=0)
    free_ai_max_output_tokens: int = Field(default=4096, gt=0)
    free_ai_global_daily_budget_usd: str = "0"
    free_ai_global_monthly_budget_usd: str = "0"
    free_ai_request_timeout_seconds: int = Field(default=120, ge=1, le=300)
    free_ai_reservation_ttl_seconds: int = Field(default=900, ge=600)
    free_ai_deepseek_fallback_to_qwen: bool = False
    qwen_enabled: bool = True
    qwen_api_key: SecretStr | None = None
    qwen_model: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_input_cost_per_million: str = "0"
    qwen_output_cost_per_million: str = "0"
    deepseek_enabled: bool = True
    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_input_cost_per_million: str = "0"
    deepseek_output_cost_per_million: str = "0"
    # Institutional Gemini for the beta: free tier only, so rates must stay at zero and limits are request-based.
    gemini_enabled: bool = True
    gemini_api_key: SecretStr | None = None
    gemini_model: str = ""
    gemini_input_cost_per_million: str = "0"
    gemini_output_cost_per_million: str = "0"
    # Invitation delivery, exclusively from backend. Disabled until configured.
    public_base_url: str = ""
    # Sandbox top-ups only. No live-mode switch exists in this prototype.
    stripe_test_enabled: bool = False
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: str = "starttls"
    smtp_username: str = ""
    smtp_password: SecretStr | None = None
    smtp_from: str = ""
    smtp_timeout_seconds: int = Field(default=15, ge=1, le=30)
    beta_invitation_days: int = Field(default=7, ge=1, le=30)
    beta_invitation_daily_limit: int = Field(default=50, ge=1)
    beta_invitation_cooldown_seconds: int = Field(default=300, ge=60)
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
    model_config = SettingsConfigDict(env_prefix="EDUCREA_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    overrides: dict[str, str] = {}
    database_url_file = os.environ.get("EDUCREA_DATABASE_URL_FILE")
    if database_url_file:
        overrides["database_url"] = Path(database_url_file).read_text().strip()
    credential_keys_file = os.environ.get("EDUCREA_CREDENTIAL_KEYS_FILE")
    if credential_keys_file:
        overrides["credential_keys"] = Path(credential_keys_file).read_text().strip()
    oidc_secret_file = os.environ.get("EDUCREA_OIDC_CLIENT_SECRET_FILE")
    if oidc_secret_file:
        overrides["oidc_client_secret"] = Path(oidc_secret_file).read_text().strip()
    for name in ("gemini_api_key", "qwen_api_key", "deepseek_api_key", "smtp_password", "stripe_secret_key", "stripe_webhook_secret"):
        path = os.environ.get(f"EDUCREA_{name.upper()}_FILE")
        if path:
            overrides[name] = Path(path).read_text().strip()
    return Settings(**overrides)

