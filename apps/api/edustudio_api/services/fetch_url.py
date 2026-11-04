"""Fetch a public document by URL for ingestion as a reference source.

Protections against SSRF (the server must never be used to reach the internal network):
- https (and http only if EDUSTUDIO_ALLOW_INSECURE_URLS=true), standard ports, no credentials in the URL;
- every host name is resolved and *every* address must be public (no loopback, private, link-local, reserved);
- redirects are followed manually (max 3) and each hop is validated again;
- content type must be HTML, plain text, Markdown or PDF; size and time are capped.
"""

import ipaddress
import re
import socket
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from ..config import get_settings

MAX_BYTES = 25 * 1024 * 1024
TIMEOUT = 20
MAX_REDIRECTS = 3
ALLOWED_TYPES = {
    "text/html": ".html", "application/xhtml+xml": ".html", "text/plain": ".txt", "text/markdown": ".md",
    "application/pdf": ".pdf",
}
USER_AGENT = "EduStudio/0.1 (reference source ingestion)"
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def client() -> httpx.Client:  # replaced in tests
    return httpx.Client(timeout=TIMEOUT, follow_redirects=False, headers={"User-Agent": USER_AGENT})


def resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(422, "No se ha podido resolver el dominio de la URL") from exc
    return sorted({info[4][0] for info in infos})


def is_public(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    # Only globally routable addresses: excludes loopback, private, link-local, CGNAT, documentation and reserved.
    return ip.is_global


def validate(url: str) -> str:
    parts = urlsplit(url.strip())
    schemes = ("https", "http") if get_settings().allow_insecure_urls else ("https",)
    if parts.scheme not in schemes:
        raise HTTPException(422, "La URL debe empezar por https://" if parts.scheme == "http"
                            else "Solo se admiten URL http(s)")
    if not parts.hostname or "@" in parts.netloc:
        raise HTTPException(422, "URL no válida")
    if parts.port not in (None, 80, 443):
        raise HTTPException(422, "La URL usa un puerto no permitido")
    addresses = resolve(parts.hostname)
    if not addresses or not all(is_public(address) for address in addresses):
        raise HTTPException(422, "Esa URL apunta a una dirección interna; no se puede descargar")
    return url.strip()


def fetch(url: str) -> tuple[str, str, bytes]:
    """Returns (final URL, extension, bytes)."""
    current = validate(url)
    with client() as http:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                with http.stream("GET", current) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise HTTPException(502, "La URL redirige a un destino no válido")
                        current = validate(str(httpx.URL(current).join(location)))
                        continue
                    if response.status_code == 404:
                        raise HTTPException(422, "La URL no existe (404)")
                    if response.status_code >= 400:
                        raise HTTPException(502, f"El servidor de la URL respondió {response.status_code}")
                    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
                    if content_type not in ALLOWED_TYPES:
                        raise HTTPException(422, "La URL no es HTML, texto, Markdown ni PDF")
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise HTTPException(413, "El documento de la URL supera los 25 MB")
                        chunks.append(chunk)
                    return current, ALLOWED_TYPES[content_type], b"".join(chunks)
            except httpx.TimeoutException as exc:
                raise HTTPException(504, "La URL ha tardado demasiado en responder") from exc
            except httpx.RequestError as exc:
                raise HTTPException(502, "No se ha podido descargar la URL") from exc
    raise HTTPException(502, "Demasiadas redirecciones")


def filename(url: str, extension: str) -> str:
    name = urlsplit(url).path.rsplit("/", 1)[-1] or "documento"
    name = re.sub(r"[^A-Za-z0-9._-]", "-", name)[:120] or "documento"
    return name if "." in name else name + extension


def suggested_title(data: bytes, extension: str, fallback: str) -> str:
    if extension == ".html":
        match = TITLE.search(data.decode("utf-8", errors="replace"))
        if match:
            title = " ".join(match.group(1).split())
            if title:
                return title[:200]
    return fallback
