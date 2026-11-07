"""Gemini native image generation (Nano Banana) for BYOK accounts.

This is deliberately separate from the text provider: image models use the
Interactions API, return an inline image instead of text, and are billed per
image rather than per token.
"""
import base64
import binascii
from dataclasses import dataclass

import httpx

from .base import ProviderError

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVISION = "2026-05-20"
ALLOWED_ASPECT_RATIOS = ("1:1", "4:3", "3:4", "16:9", "9:16")
ALLOWED_SIZES = ("1K",)


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    media_type: str


def payload(model: str, prompt: str, aspect_ratio: str = "1:1", size: str = "1K") -> dict:
    if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
        raise ProviderError("Proporción de imagen no válida", 422)
    if size not in ALLOWED_SIZES:
        raise ProviderError("Resolución de imagen no válida", 422)
    return {
        "model": model,
        "input": [{"type": "text", "text": prompt}],
        "response_format": {
            "type": "image",
            "mime_type": "image/png",
            "aspect_ratio": aspect_ratio,
            "image_size": size,
        },
    }


def _image_block(value) -> dict | None:
    if isinstance(value, dict):
        data = value.get("data")
        mime = value.get("mime_type") or value.get("mimeType")
        if isinstance(data, str) and isinstance(mime, str) and mime.startswith("image/"):
            return value
        for item in value.values():
            found = _image_block(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _image_block(item)
            if found is not None:
                return found
    return None


class GeminiImageProvider:
    def __init__(self, client: httpx.AsyncClient | None = None, timeout: int = 120) -> None:
        self.client = client
        self.timeout = timeout

    @staticmethod
    def check_response(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise ProviderError(
                "Gemini no ha aceptado la generación de imagen: el nivel gratuito no incluye imágenes o se ha "
                "alcanzado la cuota. Activa la facturación en Google AI Studio.", 429)
        if response.status_code in (401, 403):
            raise ProviderError("Gemini ha rechazado la clave o el modelo de imagen no está permitido para tu cuenta", 403)
        if response.status_code == 404:
            raise ProviderError("Gemini no reconoce ese modelo de imagen", 502)
        if response.status_code == 400:
            raise ProviderError("Gemini no ha aceptado la petición de imagen (revisa el contenido del prompt)", 422)
        if response.status_code >= 400:
            raise ProviderError("Gemini no pudo generar la imagen", 502)

    async def generate(self, api_key: str, model: str, prompt: str,
                       aspect_ratio: str = "1:1", size: str = "1K") -> GeneratedImage:
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(ENDPOINT, headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
                "Api-Revision": API_REVISION,
            }, json=payload(model, prompt, aspect_ratio, size))
            self.check_response(response)
            data = response.json()
            block = _image_block(data)
            if block is None:
                raise ProviderError("Gemini no devolvió ninguna imagen. Prueba otra descripción.", 422)
            try:
                raw = base64.b64decode(block["data"], validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ProviderError("Gemini devolvió una imagen no válida", 502) from exc
            if not raw:
                raise ProviderError("Gemini devolvió una imagen vacía", 502)
            return GeneratedImage(raw, block["mime_type"])
        except httpx.TimeoutException as exc:
            raise ProviderError("Gemini tardó demasiado en generar la imagen", 504) from exc
        except (httpx.RequestError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Error de comunicación con Gemini al generar la imagen") from exc
        finally:
            if self.client is None:
                await client.aclose()


def get_gemini_image_provider() -> GeminiImageProvider:
    from ....config import get_settings
    return GeminiImageProvider(timeout=get_settings().image_request_timeout_seconds)
