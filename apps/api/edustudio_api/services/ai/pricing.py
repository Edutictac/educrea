"""Administrator-approved paid model prices in micro-USD per million tokens."""

import json
from dataclasses import dataclass

from fastapi import HTTPException

from ...config import get_settings

PAID_PROVIDERS = ("gemini", "openrouter", "groq", "openai", "anthropic")
MAX_OUTPUT_TOKENS = 8192


@dataclass(frozen=True)
class Price:
    input_rate: int
    output_rate: int


def catalog() -> dict[str, dict[str, Price]]:
    from .providers.registry import MODEL_ID

    try:
        raw = json.loads(get_settings().paid_models_json)
        if not isinstance(raw, dict):
            raise ValueError("catalog")
        parsed: dict[str, dict[str, Price]] = {}
        for provider, models in raw.items():
            if provider not in PAID_PROVIDERS or not isinstance(models, dict):
                raise ValueError("provider")
            parsed[provider] = {}
            for model, rates in models.items():
                if not MODEL_ID.fullmatch(model) or not isinstance(rates, dict):
                    raise ValueError("model")
                input_rate, output_rate = rates.get("input"), rates.get("output")
                if (type(input_rate) is not int or type(output_rate) is not int or
                        not 0 < input_rate <= 100000000 or not 0 < output_rate <= 100000000):
                    raise ValueError("rates")
                parsed[provider][model] = Price(input_rate, output_rate)
        return parsed
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Catálogo de precios de IA no válido") from exc


def price_for(provider: str, model: str) -> Price:
    price = catalog().get(provider, {}).get(model)
    if price is None:
        raise HTTPException(403, "Modelo de pago no habilitado")
    return price


def cost(input_tokens: int, output_tokens: int, price: Price) -> int:
    return ((input_tokens * price.input_rate + output_tokens * price.output_rate + 999999) // 1000000)


def estimate(prompt: str, price: Price) -> dict:
    # One UTF-8 byte per input token plus a large allowance for framing.
    max_input_tokens = len(prompt.encode("utf-8")) + 1024
    return {"max_input_tokens": max_input_tokens, "max_output_tokens": MAX_OUTPUT_TOKENS,
            "maximum_cost_microusd": cost(max_input_tokens, MAX_OUTPUT_TOKENS, price),
            "input_rate_microusd": price.input_rate, "output_rate_microusd": price.output_rate}
