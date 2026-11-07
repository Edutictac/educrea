import httpx
import pytest
from fastapi.testclient import TestClient

from educrea_api.config import get_settings
from educrea_api.services import fetch_url
from test_sources import CURRICULUM, project, upload

HTML = f"<html><head><title>Currículum de Primària</title></head><body><h1>Currículum</h1><p>{CURRICULUM}</p></body></html>".encode()


def fake_net(routes: dict[str, httpx.Response]):
    """MockTransport keyed by URL, with an injectable resolver that returns public addresses."""
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(str(request.url), httpx.Response(404))
    return handler


@pytest.fixture
def network(monkeypatch):
    monkeypatch.setattr(fetch_url, "resolve", lambda host: ["93.184.216.34"])
    routes = {"https://samuelsoriano.es/curriculo/primaria/": httpx.Response(
        200, headers={"content-type": "text/html; charset=utf-8"}, content=HTML)}
    monkeypatch.setattr(fetch_url, "client", lambda: httpx.Client(transport=httpx.MockTransport(fake_net(routes))))
    return routes


def test_url_source_is_downloaded_ingested_and_refreshable(client: TestClient, network):
    headers, base, _ = project(client)
    created = client.post(f"{base}/sources/url", headers=headers,
                          json={"url": "https://samuelsoriano.es/curriculo/primaria/"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == "Currículum de Primària" and body["url"] == "https://samuelsoriano.es/curriculo/primaria/"
    assert body["chunk_count"] > 5 and body["fetched_at"]
    found = client.get(f"{base}/sources/{body['id']}/search", params={"q": "notas musicales pentagrama"}).json()
    assert found and "pentagrama" in found[0]["text"]
    refreshed = client.post(f"{base}/sources/{body['id']}/refresh", headers=headers)
    assert refreshed.status_code == 200 and refreshed.json()["chunk_count"] == body["chunk_count"]
    assert client.post(f"{base}/sources/url", json={"url": "https://x.test/a"}).status_code == 403  # CSRF
    # a source created by upload cannot be refreshed
    upload(client, headers, base, "notas.md", b"# Notas\n\nContenido suficiente para una fuente.")
    uploaded = next(s for s in client.get(f"{base}/sources").json() if s["url"] is None)
    assert client.post(f"{base}/sources/{uploaded['id']}/refresh", headers=headers).status_code == 409


def test_ssrf_protections(monkeypatch):
    for host, addresses in {
        "localhost": ["127.0.0.1"], "interno.test": ["10.0.0.7"], "metadata.test": ["169.254.169.254"],
        "v6.test": ["::1"], "cgnat.test": ["100.64.0.1"],
    }.items():
        monkeypatch.setattr(fetch_url, "resolve", lambda _host, values=addresses: values)
        with pytest.raises(Exception) as caught:
            fetch_url.fetch(f"https://{host}/x")
        assert "interna" in str(caught.value) or "no se puede" in str(caught.value)
    for bad in ("http://example.org/x", "file:///etc/passwd", "https://user:pass@example.org/x",
                "https://example.org:8080/x", "javascript:alert(1)"):
        with pytest.raises(Exception):
            fetch_url.validate(bad)


def test_redirects_are_revalidated_and_content_type_filtered(client: TestClient, monkeypatch):
    monkeypatch.setattr(fetch_url, "resolve",
                        lambda host: ["127.0.0.1"] if host == "interno.test" else ["93.184.216.34"])
    routes = {
        "https://publico.test/a": httpx.Response(302, headers={"location": "https://interno.test/secret"}),
        "https://publico.test/b": httpx.Response(200, headers={"content-type": "image/png"}, content=b"\x89PNG"),
        "https://publico.test/c": httpx.Response(200, headers={"content-type": "application/pdf"},
                                                 content=b"x" * (fetch_url.MAX_BYTES + 1)),
        "https://publico.test/d": httpx.Response(301, headers={"location": "https://publico.test/a"}),
    }
    monkeypatch.setattr(fetch_url, "client", lambda: httpx.Client(transport=httpx.MockTransport(fake_net(routes))))
    headers, base, _ = project(client)
    for url, expected in (("https://publico.test/a", 422), ("https://publico.test/b", 422),
                          ("https://publico.test/c", 413), ("https://publico.test/d", 422)):
        response = client.post(f"{base}/sources/url", headers=headers, json={"url": url})
        assert response.status_code == expected, (url, response.text)


def test_http_only_when_explicitly_allowed(monkeypatch):
    monkeypatch.setattr(fetch_url, "resolve", lambda host: ["93.184.216.34"])
    with pytest.raises(Exception):
        fetch_url.validate("http://samuelsoriano.es/x")
    monkeypatch.setattr(get_settings(), "allow_insecure_urls", True)
    assert fetch_url.validate("http://samuelsoriano.es/x").startswith("http://")
