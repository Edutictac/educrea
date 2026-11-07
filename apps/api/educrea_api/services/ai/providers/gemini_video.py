"""Gemini Omni Flash video generation for BYOK accounts.

The Interactions REST API returns the MP4 inside ``steps[].content[]`` with
``type: video``; the SDK-only ``output_video`` shortcut is not available here.
"""
import base64
import binascii
from dataclasses import dataclass

import httpx

from .base import ProviderError

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
ALLOWED_ASPECT_RATIOS = ("16:9", "9:16")
ALLOWED_RESOLUTIONS = ("360p", "720p")
ALLOWED_DURATIONS = (4, 5, 6)


@dataclass(frozen=True)
class GeneratedVideo:
    data: bytes
    media_type: str


def payload(model: str, prompt: str, aspect_ratio: str = "16:9", resolution: str = "360p",
            duration: int = 6) -> dict:
    if aspect_ratio not in ALLOWED_ASPECT_RATIOS:
        raise ProviderError("Proporción de vídeo no válida", 422)
    if resolution not in ALLOWED_RESOLUTIONS:
        raise ProviderError("Resolución de vídeo no válida", 422)
    if duration not in ALLOWED_DURATIONS:
        raise ProviderError("Duración de vídeo no válida", 422)
    return {
        "model": model,
        "input": prompt,
        "response_format": {
            "type": "video",
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "duration": f"{duration}s",
        },
    }


def _video_block(value) -> dict | None:
    if isinstance(value, dict):
        data = value.get("data")
        mime = value.get("mime_type") or value.get("mimeType")
        if isinstance(data, str) and isinstance(mime, str) and mime.startswith("video/"):
            return value
        for item in value.values():
            found = _video_block(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _video_block(item)
            if found is not None:
                return found
    return None



def google_reason(response: httpx.Response) -> str:
    """Google's own explanation of a rejected request (never contains the key), shortened for the teacher."""
    try:
        message = response.json().get("error", {}).get("message", "")
    except ValueError:
        return ""
    return message.strip()[:300] if isinstance(message, str) else ""

class GeminiVideoProvider:
    def __init__(self, client: httpx.AsyncClient | None = None, timeout: int = 300) -> None:
        self.client = client
        self.timeout = timeout

    @staticmethod
    def check_response(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise ProviderError(
                "Gemini no ha aceptado la generación de vídeo: el nivel gratuito no incluye vídeo o se ha "
                "alcanzado la cuota. Activa la facturación en Google AI Studio.", 429)
        if response.status_code in (401, 403):
            raise ProviderError("Gemini ha rechazado la clave o el modelo de vídeo no está permitido para tu cuenta", 403)
        if response.status_code == 404:
            raise ProviderError("Gemini no reconoce ese modelo de vídeo", 502)
        if response.status_code == 400:
            raise ProviderError(f"Gemini no ha aceptado la petición de vídeo ({google_reason(response) or 'revisa el prompt y la duración'})", 422)
        if response.status_code >= 400:
            raise ProviderError("Gemini no pudo generar el vídeo", 502)

    async def generate(self, api_key: str, model: str, prompt: str, aspect_ratio: str = "16:9",
                       resolution: str = "360p", duration: int = 6) -> GeneratedVideo:
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.post(ENDPOINT, headers={
                "x-goog-api-key": api_key, "Content-Type": "application/json",
            }, json=payload(model, prompt, aspect_ratio, resolution, duration))
            self.check_response(response)
            data = response.json()
            block = _video_block(data)
            if block is None:
                raise ProviderError("Gemini no devolvió ningún vídeo. Prueba otra descripción.", 422)
            try:
                raw = base64.b64decode(block["data"], validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ProviderError("Gemini devolvió un vídeo no válido", 502, consumed_unknown=True) from exc
            if not raw:
                raise ProviderError("Gemini devolvió un vídeo vacío", 502, consumed_unknown=True)
            return GeneratedVideo(raw, block["mime_type"])
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            # The request never reached Google: nothing was billed.
            raise ProviderError("No se ha podido conectar con Gemini para generar el vídeo", 502) from exc
        except httpx.TimeoutException as exc:
            # Sent but unanswered: Google may still have generated and billed the video.
            raise ProviderError("Gemini tardó demasiado en generar el vídeo", 504, consumed_unknown=True) from exc
        except httpx.RequestError as exc:
            raise ProviderError("Error de comunicación con Gemini al generar el vídeo", 502,
                                consumed_unknown=True) from exc
        except (ValueError, KeyError, TypeError) as exc:
            # A 200 response we could not read: the video was generated and billed.
            raise ProviderError("Gemini devolvió una respuesta que no se puede leer", 502, consumed_unknown=True) from exc
        finally:
            if self.client is None:
                await client.aclose()


def get_gemini_video_provider() -> GeminiVideoProvider:
    from ....config import get_settings
    return GeminiVideoProvider(timeout=get_settings().video_request_timeout_seconds)
