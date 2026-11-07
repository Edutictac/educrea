"""Only administrator-listed free models can be used."""

import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ....config import get_settings
from .compatible import CompatibleProvider
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider, free_models as gemini_free_models
from ..temporary_credentials import credential as temporary_credential
from ..credentials import decrypt_key, personal_credential

MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")
PROVIDERS = ("gemini", "mistral", "openrouter", "groq", "ollama", "openai", "anthropic", "deepseek")
# Order used to pick the first confirmed free model and to fall back when one is saturated (429/503).
FREE_PROVIDERS = ("gemini", "groq", "openrouter", "ollama")


def free_models(provider: str) -> list[str]:
    if provider == "gemini":
        return gemini_free_models()
    if provider == "mistral":
        return []  # Current Mistral API requires billing activation; never advertise it as free.
    if provider not in PROVIDERS:
        return []
    settings = get_settings()
    configured = getattr(settings, f"{provider}_free_models", "")
    if provider == "ollama" and not settings.ollama_base_url:
        return []
    return [value for value in dict.fromkeys(part.strip() for part in configured.split(","))
            if MODEL_ID.fullmatch(value)]


def status(db: Session, user_id: UUID, provider: str) -> dict:
    from ..pricing import catalog

    credential = personal_credential(db, user_id, provider) if provider != "ollama" else None
    models = free_models(provider)
    temporary = temporary_credential(db, user_id, provider)
    return {"configured": bool(temporary) or credential is not None if provider != "ollama" else bool(models),
            "verified_free_models": models,
            "confirmed_free_models": [model for model in models if provider == "ollama" or
                                      (credential and model in credential.free_confirmations) or (temporary and model in temporary['confirmed'])],
            "paid_models": [{"model": model, "input_rate_microusd": price.input_rate,
                             "output_rate_microusd": price.output_rate}
                            for model, price in catalog().get(provider, {}).items()]}


def authorize(db: Session, user_id: UUID, provider: str, model: str) -> str:
    if model not in free_models(provider):
        raise HTTPException(403, "Modelo no autorizado en modo gratuito")
    if provider == "ollama":
        return ""
    temporary = temporary_credential(db, user_id, provider)
    if temporary:
        if model not in temporary['confirmed']:
            raise HTTPException(403, "Confirma la gratuidad del modelo para esta sesión")
        return temporary['key'].get_secret_value()
    credential = personal_credential(db, user_id, provider)
    if credential is None:
        raise HTTPException(409, f"Configura tu clave de {provider} antes de generar")
    if model not in credential.free_confirmations:
        raise HTTPException(403, "Confirma la gratuidad del modelo para tu cuenta antes de generar")
    return decrypt_key(credential.ciphertext)


def authorize_paid(db: Session, user_id: UUID, provider: str, model: str) -> str:
    from ..pricing import price_for

    price_for(provider, model)
    temporary = temporary_credential(db, user_id, provider)
    if temporary:
        return temporary['key'].get_secret_value()
    credential = personal_credential(db, user_id, provider)
    if credential is None:
        raise HTTPException(409, f"Configura tu clave de {provider} antes de generar")
    return decrypt_key(credential.ciphertext)


def adapter(provider: str):
    if provider == "gemini":
        return GeminiProvider()
    if provider == "ollama":
        return CompatibleProvider(provider, base_url=get_settings().ollama_base_url)
    if provider == "anthropic":
        return AnthropicProvider()
    return CompatibleProvider(provider)


def preferred_free(db: Session, user_id: UUID, provider: str | None, model: str | None) -> tuple[str, str, str] | None:
    """The free model the teacher picked in the selector, or the first confirmed one when «Automática»."""
    if provider and model:
        if provider not in FREE_PROVIDERS:
            raise HTTPException(422, "Elige una IA gratuita en el selector")
        return provider, model, authorize(db, user_id, provider, model)
    return first_free(db, user_id)


def first_free(db: Session, user_id: UUID) -> tuple[str, str, str] | None:
    """First provider/model already confirmed as free by this user, in the documented order."""
    return fallback(db, user_id, set())


def next_free(db: Session, user_id: UUID, skip_providers: set[str] | None = None,
              skip_models: set[tuple[str, str]] | None = None,
              prefer_provider: str | None = None) -> tuple[str, str, str] | None:
    """Next confirmed free model, skipping whole providers (quota) or single models (truncated/invalid).

    When a model fails but its provider still works, its other models are tried first.
    """
    skip_providers = skip_providers or set()
    skip_models = skip_models or set()
    order = [provider for provider in FREE_PROVIDERS
             if provider not in skip_providers and provider != prefer_provider]
    if prefer_provider in FREE_PROVIDERS and prefer_provider not in skip_providers:
        order.insert(0, prefer_provider)
    for provider in order:
        for model in status(db, user_id, provider)["confirmed_free_models"]:
            if (provider, model) in skip_models:
                continue
            return provider, model, authorize(db, user_id, provider, model)
    return None


def fallback(db: Session, user_id: UUID, excluded: set[str]) -> tuple[str, str, str] | None:
    return next_free(db, user_id, skip_providers=excluded)
