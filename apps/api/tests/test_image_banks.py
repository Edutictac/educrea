from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from educrea_api.services import image_banks
from test_ai import setup_user

FIXTURES = Path(__file__).parent / "fixtures"
PNG = (FIXTURES / "trompeta.png").read_bytes()


def install(monkeypatch, handler):
    monkeypatch.setattr(image_banks, "client", lambda: httpx.Client(transport=httpx.MockTransport(handler)))


def search_ok(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/pictograms/ca/search/casa"):
        return httpx.Response(200, json=[{"_id": 2249, "keywords": [{"keyword": "casa"}, {"keyword": "edificio"}]}])
    if request.url.path.endswith("/pictograms/es/search/nada"):
        return httpx.Response(200, json=[])
    return httpx.Response(404)


def images_ok(request: httpx.Request) -> httpx.Response:
    if request.url.host == "static.arasaac.org":
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    return httpx.Response(404)


def test_search_maps_languages_and_normalises_results(client: TestClient, monkeypatch):
    install(monkeypatch, search_ok)
    headers, project_id = setup_user(client)
    result = client.get("/api/image-banks/arasaac/search", params={"q": "casa", "language": "va"})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["license"] == "CC BY-NC-SA 4.0" and data["commercial_use"] is False
    item = data["items"][0]
    assert item["id"] == 2249 and item["title"] == "casa"
    assert item["thumbnail_url"] == "/api/image-banks/arasaac/2249/thumbnail"
    assert "Sergio Palao" in item["credit"] and "arasaac.org/pictograms/2249" in item["credit"]
    assert client.get("/api/image-banks/arasaac/search", params={"q": "nada"}).json()["items"] == []
    assert client.get("/api/image-banks/arasaac/search", params={"q": ""}).status_code == 422
    assert client.get("/api/image-banks/arasaac/search", params={"q": "casa", "language": "xx"}).status_code == 200


def test_thumbnail_and_content_are_proxied_as_png(client: TestClient, monkeypatch):
    install(monkeypatch, images_ok)
    headers, project_id = setup_user(client)
    for size in ("thumbnail", "content"):
        response = client.get(f"/api/image-banks/arasaac/2249/{size}")
        assert response.status_code == 200 and response.content == PNG
        assert response.headers["content-type"] == "image/png"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "sandbox" in response.headers["content-security-policy"]


def test_import_stores_the_image_with_attribution(client: TestClient, monkeypatch):
    install(monkeypatch, images_ok)
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    created = client.post(f"{base}/assets/from-bank", headers=headers,
                          json={"provider": "arasaac", "id": 2249, "alt": "Casa"})
    assert created.status_code == 201, created.text
    asset = created.json()
    assert asset["path"] == "imagenes/arasaac-2249.png" and asset["alt"] == "Casa"
    assert "Sergio Palao" in asset["credit"] and "CC BY-NC-SA 4.0" in asset["credit"]
    assert client.get(f"{base}/assets/{asset['id']}/content").content == PNG
    md = "# Casa\n\n![Casa](imagenes/arasaac-2249.png)\n"
    file = client.post(f"{base}/files", headers=headers, json={"path": "ficha.md", "content": md}).json()
    exported = client.get(f"{base}/files/{file['id']}/export.html").text
    assert "Sergio Palao" in exported and "CC BY-NC-SA 4.0" in exported
    assert client.post(f"{base}/assets/from-bank", headers=headers,
                       json={"provider": "arasaac", "id": 2249, "alt": "Otra casa"}).status_code == 409
    assert client.post(f"{base}/assets/from-bank", json={"provider": "arasaac", "id": 2249, "alt": "x"}).status_code == 403
    assert client.post(f"{base}/assets/from-bank", headers=headers,
                       json={"provider": "otro", "id": 2249, "alt": "x"}).status_code == 422
    assert client.post(f"{base}/assets/from-bank", headers=headers,
                       json={"provider": "arasaac", "id": 2249, "alt": " "}).status_code == 422


def test_download_rejects_non_png_and_provider_errors(client: TestClient, monkeypatch):
    headers, project_id = setup_user(client)

    def html(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html></html>", headers={"content-type": "text/html"})

    install(monkeypatch, html)
    assert client.get("/api/image-banks/arasaac/2249/content").status_code == 502

    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    install(monkeypatch, broken)
    assert client.get("/api/image-banks/arasaac/search", params={"q": "casa"}).status_code == 502
    assert client.get("/api/image-banks/arasaac/2249/content").status_code == 502
    assert client.get("/api/image-banks/arasaac/0/content").status_code == 422


def test_search_requires_a_session(client: TestClient, monkeypatch):
    install(monkeypatch, search_ok)
    assert client.get("/api/image-banks/arasaac/search", params={"q": "casa"}).status_code == 401
    assert client.get("/api/image-banks").status_code == 401
