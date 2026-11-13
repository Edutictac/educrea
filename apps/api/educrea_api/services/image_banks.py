"""Free image banks searched and downloaded server-side.

ARASAAC is the first provider. The browser never contacts the provider: search, thumbnails and downloads go through
this API, so the content security policy keeps its current origins. Only PNG is accepted and every download is
checked by signature and size before it reaches the project image library.

ARASAAC pictograms are published under CC BY-NC-SA 4.0: attribution is required and commercial use is not allowed.
The credit stored with each imported image keeps the author, the licence and the source URL.
"""

from urllib.parse import quote

import httpx
from fastapi import HTTPException

PROVIDER = "arasaac"
API_URL = "https://api.arasaac.org/api"
STATIC_URL = "https://static.arasaac.org/pictograms"
SOURCE_URL = "https://arasaac.org/pictograms/{identifier}"
LICENSE = "CC BY-NC-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
CREDIT = "Sergio Palao / ARASAAC / CC BY-NC-SA 4.0"
COMMERCIAL_USE = False
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 15
MAX_RESULTS = 40
USER_AGENT = "EduCrea/0.1 (image bank)"
LANGUAGES = {"es": "es", "ca": "ca", "va": "ca", "en": "en"}


def client() -> httpx.Client:  # replaced in tests
    return httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT})


def language(value: str) -> str:
    return LANGUAGES.get((value or "").strip().lower(), "es")


def _item(row: dict, fallback: str) -> dict | None:
    try:
        identifier = int(row["_id"])
    except (KeyError, TypeError, ValueError):
        return None
    keywords: list[str] = []
    for keyword in row.get("keywords") or []:
        word = str(keyword.get("keyword", "")).strip() if isinstance(keyword, dict) else ""
        if word and word not in keywords:
            keywords.append(word)
    title = keywords[0] if keywords else fallback
    return {
        "provider": PROVIDER,
        "id": identifier,
        "title": title,
        "keywords": keywords[:8],
        "thumbnail_url": f"/api/image-banks/{PROVIDER}/{identifier}/thumbnail",
        "content_url": f"/api/image-banks/{PROVIDER}/{identifier}/content",
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "source_url": SOURCE_URL.format(identifier=identifier),
        "credit": credit_for(identifier),
        "media_type": "image/png",
    }


def search(query: str, language_code: str = "es") -> dict:
    text = (query or "").strip()
    if not text:
        raise HTTPException(422, "Escribe qué quieres buscar")
    if len(text) > 80:
        raise HTTPException(422, "La búsqueda es demasiado larga")
    url = f"{API_URL}/pictograms/{language(language_code)}/search/{quote(text, safe='')}"
    try:
        with client() as http:
            response = http.get(url)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "El banco de imágenes ha tardado demasiado en responder") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "No se ha podido consultar el banco de imágenes") from exc
    if response.status_code == 404:
        return {"provider": PROVIDER, "license": LICENSE, "license_url": LICENSE_URL,
                "commercial_use": COMMERCIAL_USE, "items": []}
    if response.status_code >= 400:
        raise HTTPException(502, f"El banco de imágenes respondió {response.status_code}")
    try:
        rows = response.json()
    except ValueError as exc:
        raise HTTPException(502, "El banco de imágenes devolvió una respuesta ilegible") from exc
    if not isinstance(rows, list):
        raise HTTPException(502, "El banco de imágenes devolvió una respuesta inesperada")
    items = [item for row in rows[:MAX_RESULTS] if isinstance(row, dict) if (item := _item(row, text)) is not None]
    return {"provider": PROVIDER, "license": LICENSE, "license_url": LICENSE_URL,
            "commercial_use": COMMERCIAL_USE, "items": items}


def credit_for(identifier: int) -> str:
    return f"{CREDIT} · {SOURCE_URL.format(identifier=identifier)}"


def pictogram(identifier: int, size: int = 500) -> bytes:
    if identifier < 1 or identifier > 10_000_000:
        raise HTTPException(422, "Pictograma no válido")
    url = f"{STATIC_URL}/{identifier}/{identifier}_{size}.png"
    chunks: list[bytes] = []
    total = 0
    try:
        with client() as http:
            with http.stream("GET", url) as response:
                if response.status_code == 404:
                    raise HTTPException(404, "Pictograma no encontrado")
                if response.status_code >= 400:
                    raise HTTPException(502, f"El banco de imágenes respondió {response.status_code}")
                media_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
                if media_type != "image/png":
                    raise HTTPException(502, "El banco de imágenes no devolvió un PNG")
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise HTTPException(413, "La imagen del banco supera los 2 MB")
                    chunks.append(chunk)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "El banco de imágenes ha tardado demasiado en responder") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "No se ha podido descargar la imagen del banco") from exc
    data = b"".join(chunks)
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(502, "El banco de imágenes no devolvió un PNG válido")
    return data
