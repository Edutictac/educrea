import json
import re
from collections.abc import AsyncIterator

import httpx

from .base import ProviderChunk, ProviderError, ProviderResult

MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "changes": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "path": {"type": "STRING"}, "content": {"type": "STRING"}},
            "required": ["path", "content"]}},
        "citations": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "chunk": {"type": "STRING"}, "quote": {"type": "STRING"}, "used_for": {"type": "STRING"}},
            "required": ["quote"]}},
        "not_covered": {"type": "ARRAY", "items": {"type": "STRING"}},
        "dua": {"type": "OBJECT", "properties": {
            "barriers": {"type": "ARRAY", "items": {"type": "STRING"}},
            "measures": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "principle": {"type": "STRING", "enum": ["representacion", "accion_expresion", "implicacion"]},
                "barrier": {"type": "STRING"}, "measure": {"type": "STRING"}},
                "required": ["principle", "measure"]}}}},
        "tool_calls": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "name": {"type": "STRING"}, "arguments_json": {"type": "STRING"}}, "required": ["name"]}},
    },
    "required": ["summary", "changes"],
}


def free_models() -> list[str]:
    from ....config import get_settings

    models = [model.strip() for model in get_settings().gemini_free_models.split(",") if model.strip()]
    return [model for model in dict.fromkeys(models) if MODEL_ID.fullmatch(model)]


def payload(prompt: str) -> dict:
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "maxOutputTokens": 8192,
            "temperature": 0.2,
        },
    }


def usage_from(data: dict) -> dict[str, int]:
    value = data.get("usageMetadata") or {}
    return {
        "input_tokens": int(value.get("promptTokenCount") or 0),
        "output_tokens": int(value.get("candidatesTokenCount") or 0),
    }


class GeminiProvider:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    @staticmethod
    def url(model: str, stream: bool = False) -> str:
        if not MODEL_ID.fullmatch(model):
            raise ProviderError("Modelo no válido", 422)
        suffix = ":streamGenerateContent?alt=sse" if stream else ":generateContent"
        return f"{BASE_URL}/{model}{suffix}"

    @staticmethod
    def check_response(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise ProviderError("Cuota o límite de Gemini alcanzado", 429)
        if response.status_code == 503:
            raise ProviderError("Gemini está saturado ahora mismo. Reintenta en un momento o elige otro modelo", 503)
        if response.status_code in (401, 403):
            raise ProviderError("Gemini ha rechazado la clave o el modelo no está permitido para tu cuenta", 502)
        if response.status_code == 404:
            raise ProviderError("Gemini no reconoce ese modelo", 502)
        if response.status_code >= 400:
            raise ProviderError("Gemini no pudo completar la solicitud", 502)

    async def generate(self, api_key: str, model: str, prompt: str) -> ProviderResult:
        client = self.client or httpx.AsyncClient(timeout=90)
        try:
            response = await client.post(self.url(model), headers={"x-goog-api-key": api_key}, json=payload(prompt))
            self.check_response(response)
            data = response.json()
            candidates = data.get("candidates") or []
            if not candidates or candidates[0].get("finishReason") != "STOP":
                raise ProviderError("Respuesta incompleta de Gemini")
            text = "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", []))
            if not text:
                raise ProviderError("Respuesta vacía de Gemini")
            return ProviderResult(text=text, usage=usage_from(data))
        except httpx.TimeoutException as exc:
            raise ProviderError("Gemini tardó demasiado en responder. Prueba otro modelo", 504) from exc
        except (httpx.RequestError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Error de comunicación con Gemini") from exc
        finally:
            if self.client is None:
                await client.aclose()

    async def stream(self, api_key: str, model: str, prompt: str) -> AsyncIterator[ProviderChunk]:
        client = self.client or httpx.AsyncClient(timeout=90)
        finished = False
        try:
            async with client.stream("POST", self.url(model, stream=True),
                                     headers={"x-goog-api-key": api_key}, json=payload(prompt)) as response:
                self.check_response(response)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        data = json.loads(line[5:].strip())
                        candidates = data.get("candidates") or []
                        candidate = candidates[0] if candidates else {}
                        text = "".join(part.get("text", "") for part in candidate.get("content", {}).get("parts", []))
                        reason = candidate.get("finishReason")
                        if reason and reason != "STOP":
                            raise ProviderError("Respuesta incompleta de Gemini")
                        finished = finished or reason == "STOP"
                        yield ProviderChunk(text=text, usage=usage_from(data), finished=reason == "STOP")
                    except (ValueError, KeyError, TypeError) as exc:
                        raise ProviderError("Respuesta incompleta de Gemini") from exc
            if not finished:
                raise ProviderError("Respuesta incompleta de Gemini")
        except httpx.TimeoutException as exc:
            raise ProviderError("Gemini tardó demasiado en responder. Prueba otro modelo", 504) from exc
        except httpx.RequestError as exc:
            raise ProviderError("Error de comunicación con Gemini") from exc
        finally:
            if self.client is None:
                await client.aclose()


def get_gemini_provider() -> GeminiProvider:
    return GeminiProvider()

