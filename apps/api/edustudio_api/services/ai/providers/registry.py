"""Only administrator-listed free models can be used."""

import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ....config import get_settings
from .compatible import CompatibleProvider
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider, free_models as gemini_free_models
from ..credentials import decrypt_key, personal_credential

MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")
PROVIDERS = ("gemini", "mistral", "openrouter", "groq", "nvidia", "ollama", "openai", "anthropic")
# Order used to pick the first confirmed free model and to fall back when one is saturated (429/503).
FREE_PROVIDERS = ("gemini", "mistral", "nvidia", "groq", "openrouter", "ollama")


def free_models(provider: str) -> list[str]:
    if provider == "gemini":
        return gemini_free_models()
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
    return {"configured": credential is not None if provider != "ollama" else bool(models),
            "verified_free_models": models,
            "confirmed_free_models": [model for model in models if provider == "ollama" or
                                      (credential and model in credential.free_confirmations)],
            "paid_models": [{"model": model, "input_rate_microusd": price.input_rate,
                             "output_rate_microusd": price.output_rate}
                            for model, price in catalog().get(provider, {}).items()]}


def authorize(db: Session, user_id: UUID, provider: str, model: str) -> str:
    if model not in free_models(provider):
        raise HTTPException(403, "Modelo no autorizado en modo gratuito")
    if provider == "ollama":
        return ""
    credential = personal_credential(db, user_id, provider)
    if credential is None:
        raise HTTPException(409, f"Configura tu clave de {provider} antes de generar")
    if model not in credential.free_confirmations:
        raise HTTPException(403, "Confirma la gratuidad del modelo para tu cuenta antes de generar")
    return decrypt_key(credential.ciphertext)


def authorize_paid(db: Session, user_id: UUID, provider: str, model: str) -> str:
    from ..pricing import price_for

    price_for(provider, model)
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


def fallback(db: Session, user_id: UUID, excluded: set[str]) -> tuple[str, str, str] | None:
    for provider in FREE_PROVIDERS:
        if provider in excluded:
            continue
        models = status(db, user_id, provider)["confirmed_free_models"]
        if models:
            return provider, models[0], authorize(db, user_id, provider, models[0])
    return None
