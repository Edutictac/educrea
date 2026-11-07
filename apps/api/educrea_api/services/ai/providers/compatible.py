"""Adapters for the OpenAI-compatible free text endpoints."""

import json
from collections.abc import AsyncIterator

import httpx

from ..pricing import MAX_OUTPUT_TOKENS
from .base import ProviderChunk, ProviderError, ProviderResult


URLS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "mistral": "https://api.mistral.ai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
}


def _usage(data: dict) -> dict[str, int]:
    usage = data.get("usage") or {}
    if "prompt_tokens" not in usage or "completion_tokens" not in usage:
        return {}
    return {"input_tokens": max(0, int(usage.get("prompt_tokens") or 0)),
            "output_tokens": max(0, int(usage.get("completion_tokens") or 0))}


def _check(response: httpx.Response, provider: str) -> None:
    usage = {}
    if response.status_code >= 400:
        try:
            usage = _usage(response.json())
        except (ValueError, TypeError, AttributeError):
            pass
    if response.status_code == 429:
        raise ProviderError(f"Cuota o límite de {provider} alcanzado", 429, usage=usage)
    if response.status_code in (503, 504):
        raise ProviderError(f"{provider} está saturado ahora mismo", response.status_code, usage=usage)
    if response.status_code >= 400:
        raise ProviderError(f"{provider} no pudo completar la solicitud", 502, usage=usage)


class CompatibleProvider:
    def __init__(self, name: str, client: httpx.AsyncClient | None = None, base_url: str = "",
                 endpoint: str | None = None, max_output_tokens: int | None = None,
                 extra_payload: dict | None = None) -> None:
        self.name = name
        self.client = client
        self.max_output_tokens = max_output_tokens
        self.extra_payload = extra_payload or {}
        self.url = endpoint or URLS.get(name) or f"{base_url.rstrip('/')}/api/chat"
        if name == "ollama" and not base_url:
            raise ProviderError("Ollama no está configurado", 503)

    def _payload(self, model: str, prompt: str, stream: bool) -> dict:
        if self.name == "ollama":
            return {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": stream,
                    "format": "json", "options": {"num_predict": 8192, "temperature": 0.2}}
        return {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": stream,
                ("max_completion_tokens" if self.name == "openai" else "max_tokens"):
                    self.max_output_tokens or (MAX_OUTPUT_TOKENS if self.name == "deepseek" else 16384),
                **({"thinking": {"type": "disabled"}} if self.name == "deepseek" else {}),
                **({} if self.name == "openai" else {"temperature": 0.2}),
                **({"stream_options": {"include_usage": True}} if stream else {}),
                **self.extra_payload}

    def _headers(self, api_key: str) -> dict[str, str]:
        return {} if self.name == "ollama" else {"Authorization": f"Bearer {api_key}"}

    async def generate(self, api_key: str, model: str, prompt: str) -> ProviderResult:
        client = self.client or httpx.AsyncClient(timeout=90)
        try:
            response = await client.post(self.url, headers=self._headers(api_key), json=self._payload(model, prompt, False))
            _check(response, self.name)
            data = response.json()
            if self.name == "ollama":
                text = data.get("message", {}).get("content", "")
                usage = {"input_tokens": data.get("prompt_eval_count", 0),
                         "output_tokens": data.get("eval_count", 0)}
                finished = data.get("done") is True
            else:
                choice = (data.get("choices") or [{}])[0]
                text = choice.get("message", {}).get("content", "")
                usage = _usage(data)
                reason = choice.get("finish_reason")
                finished = reason == "stop"
                if reason == "length":
                    raise ProviderError(f"{self.name} cortó la respuesta por el límite de tokens de salida", 502, truncated=True, usage=usage)
            if not finished or not isinstance(text, str) or not text:
                raise ProviderError(f"Respuesta incompleta de {self.name}", usage=usage,
                                    consumed_unknown=not bool(usage))
            return ProviderResult(text, usage)
        except httpx.TimeoutException as exc:
            raise ProviderError(f"{self.name} tardó demasiado en responder", 504, consumed_unknown=True) from exc
        except (httpx.RequestError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ProviderError(f"Error de comunicación con {self.name}", consumed_unknown=True) from exc
        finally:
            if self.client is None:
                await client.aclose()

    async def stream(self, api_key: str, model: str, prompt: str) -> AsyncIterator[ProviderChunk]:
        client = self.client or httpx.AsyncClient(timeout=90)
        finished = False
        try:
            async with client.stream("POST", self.url, headers=self._headers(api_key),
                                     json=self._payload(model, prompt, True)) as response:
                if response.status_code >= 400:
                    await response.aread()
                _check(response, self.name)
                async for line in response.aiter_lines():
                    if self.name == "ollama":
                        if not line.strip():
                            continue
                        raw = line
                    else:
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            break
                    try:
                        data = json.loads(raw)
                        if self.name == "ollama":
                            text = data.get("message", {}).get("content", "")
                            done = data.get("done") is True
                            usage = {"input_tokens": data.get("prompt_eval_count", 0),
                                     "output_tokens": data.get("eval_count", 0)} if done else {}
                        else:
                            choice = (data.get("choices") or [{}])[0]
                            text = choice.get("delta", {}).get("content") or ""
                            done = choice.get("finish_reason") == "stop"
                            usage = _usage(data) if data.get("usage") else {}
                            reason = choice.get("finish_reason")
                            if reason == "length":
                                raise ProviderError(f"{self.name} cortó la respuesta por el límite de tokens de salida", 502, truncated=True, usage=usage)
                            if reason not in (None, "stop"):
                                raise ProviderError(f"Respuesta incompleta de {self.name}", usage=usage,
                                                    consumed_unknown=not bool(usage))
                        finished = finished or done
                        yield ProviderChunk(text=text, usage=usage, finished=done)
                    except (ValueError, KeyError, TypeError, AttributeError) as exc:
                        raise ProviderError(f"Respuesta incompleta de {self.name}", consumed_unknown=True) from exc
            if not finished:
                raise ProviderError(f"Respuesta incompleta de {self.name}")
        except httpx.TimeoutException as exc:
            raise ProviderError(f"{self.name} tardó demasiado en responder", 504, consumed_unknown=True) from exc
        except httpx.RequestError as exc:
            raise ProviderError(f"Error de comunicación con {self.name}", consumed_unknown=True) from exc
        finally:
            if self.client is None:
                await client.aclose()
