"""Anthropic Messages API adapter for administrator-priced text models."""

import json
from collections.abc import AsyncIterator

import httpx

from .base import ProviderChunk, ProviderError, ProviderResult

URL = "https://api.anthropic.com/v1/messages"


class AnthropicProvider:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    async def generate(self, api_key: str, model: str, prompt: str) -> ProviderResult:
        client = self.client or httpx.AsyncClient(timeout=90)
        try:
            response = await client.post(URL, headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                                         json={"model": model, "max_tokens": 8192,
                                               "messages": [{"role": "user", "content": prompt}]})
            if response.status_code == 429:
                raise ProviderError("Cuota o límite de Anthropic alcanzado", 429)
            if response.status_code >= 400:
                raise ProviderError("Anthropic no pudo completar la solicitud")
            data = response.json()
            if data.get("stop_reason") != "end_turn":
                raise ProviderError("Respuesta incompleta de Anthropic")
            content = data.get("content") or []
            text = "".join(part.get("text", "") for part in content if part.get("type") == "text")
            if not text:
                raise ProviderError("Respuesta vacía de Anthropic")
            usage = data.get("usage") or {}
            return ProviderResult(text, {"input_tokens": max(0, int(usage.get("input_tokens") or 0)),
                                         "output_tokens": max(0, int(usage.get("output_tokens") or 0))})
        except (httpx.RequestError, ValueError, TypeError, AttributeError) as exc:
            raise ProviderError("Error de comunicación con Anthropic") from exc
        finally:
            if self.client is None:
                await client.aclose()

    async def stream(self, api_key: str, model: str, prompt: str) -> AsyncIterator[ProviderChunk]:
        client = self.client or httpx.AsyncClient(timeout=90)
        input_tokens = 0
        output_tokens = 0
        finished = False
        try:
            async with client.stream("POST", URL,
                                     headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                                     json={"model": model, "max_tokens": 8192, "stream": True,
                                           "messages": [{"role": "user", "content": prompt}]}) as response:
                if response.status_code == 429:
                    raise ProviderError("Cuota o límite de Anthropic alcanzado", 429)
                if response.status_code >= 400:
                    raise ProviderError("Anthropic no pudo completar la solicitud")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        data = json.loads(line[5:].strip())
                        kind = data.get("type")
                        if kind == "error":
                            raise ProviderError("Anthropic interrumpió la respuesta")
                        if kind == "message_start":
                            input_tokens = max(0, int((data.get("message", {}).get("usage") or {}).get("input_tokens") or 0))
                        elif kind == "content_block_delta" and data.get("delta", {}).get("type") == "text_delta":
                            yield ProviderChunk(text=data["delta"].get("text", ""))
                        elif kind == "message_delta":
                            output_tokens = max(0, int((data.get("usage") or {}).get("output_tokens") or 0))
                            if data.get("delta", {}).get("stop_reason") != "end_turn":
                                raise ProviderError("Respuesta incompleta de Anthropic")
                            finished = True
                            yield ProviderChunk(usage={"input_tokens": input_tokens,
                                                       "output_tokens": output_tokens}, finished=True)
                    except (ValueError, TypeError, AttributeError, KeyError) as exc:
                        raise ProviderError("Respuesta incompleta de Anthropic") from exc
            if not finished:
                raise ProviderError("Respuesta incompleta de Anthropic")
        except httpx.RequestError as exc:
            raise ProviderError("Error de comunicación con Anthropic") from exc
        finally:
            if self.client is None:
                await client.aclose()
