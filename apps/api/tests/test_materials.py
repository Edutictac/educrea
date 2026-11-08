import io
import re
import zipfile

from fastapi.testclient import TestClient

from test_auth_projects import register

MALICIOUS = ("# Fracciones\n\n<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n"
             "[mal](javascript:alert(1)) [bien](https://example.org)\n\n![remota](https://evil.test/a.png)\n\n"
             "| a | b |\n|---|---|\n| 1 | 2 |\n")


def setup(client: TestClient, email="t@example.org"):
    headers = {"X-CSRF-Token": register(client, email)}
    project = client.post("/api/projects", headers=headers, json={"title": "Fichas"}).json()
    base = f"/api/projects/{project['id']}"
    file = client.post(f"{base}/files", headers=headers, json={"path": "ficha.md", "content": MALICIOUS}).json()
    return headers, base, file


def test_render_escapes_html_and_blocks_unsafe_links_and_remote_images(client: TestClient):
    _, base, file = setup(client)
    data = client.get(f"{base}/files/{file['id']}/render").json()
    out = data["html"]
    assert data["title"] == "Fracciones"
    assert "<script" not in out and "<img" not in out
    assert "&lt;script&gt;" in out and "&lt;img src=x onerror" in out
    assert 'href="javascript' not in out and 'href="https://example.org"' in out
    assert "evil.test" not in out and "remota" in out
    assert "<table>" in out


def test_export_html_has_restrictive_csp_and_download_headers(client: TestClient):
    _, base, file = setup(client)
    response = client.get(f"{base}/files/{file['id']}/export.html")
    assert response.status_code == 200
    assert "default-src 'none'" in response.text and "<script" not in response.text
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_render_rejects_non_markdown_and_other_owner(client: TestClient):
    headers, base, _ = setup(client)
    other = client.post(f"{base}/files", headers=headers, json={"path": "index.html", "content": "<p>x</p>"}).json()
    assert client.get(f"{base}/files/{other['id']}/render").status_code == 422
    _, base2, file2 = setup(client, "second@example.org")
    assert client.get(f"{base}/files/{file2['id']}/render").status_code == 404
    assert client.get(f"{base}/export.zip").status_code == 404


def test_zip_export_contains_project_files(client: TestClient):
    _, base, _ = setup(client)
    response = client.get(f"{base}/export.zip")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.namelist() == ["ficha.md"]


def test_docx_and_pdf_export_run_in_sandbox(client: TestClient):
    import shutil
    import pytest

    if not (shutil.which("pandoc") and shutil.which("bwrap")):
        pytest.skip("pandoc/bwrap no disponibles")
    _, base, file = setup(client)
    docx = client.get(f"{base}/files/{file['id']}/export.docx")
    assert docx.status_code == 200 and docx.content[:2] == b"PK"
    with zipfile.ZipFile(io.BytesIO(docx.content)) as archive:
        body = archive.read("word/document.xml").decode()
        everything = "".join(archive.read(name).decode("utf-8", "ignore") for name in archive.namelist()
                             if name.endswith((".xml", ".rels")))
    assert "Fracciones" in body and "<script" not in everything and "javascript:" not in everything and "evil.test" not in everything
    assert client.get(f"{base}/files/{file['id']}/export.exe").status_code == 404
    if shutil.which("xelatex"):
        pdf = client.get(f"{base}/files/{file['id']}/export.pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_docx_export_keeps_accents_in_title(client: TestClient):
    import shutil
    import pytest

    if not (shutil.which("pandoc") and shutil.which("bwrap")):
        pytest.skip("pandoc/bwrap no disponibles")
    headers = {"X-CSRF-Token": register(client, "accents@example.org")}
    project = client.post("/api/projects", headers=headers, json={"title": "Accents"}).json()
    base = f"/api/projects/{project['id']}"
    title = "Fitxa amb imatges, història de la música"
    file = client.post(f"{base}/files", headers=headers,
                       json={"path": "fitxa.md", "content": f"# {title}\n\nText amb tildes: cançó.\n"}).json()
    docx = client.get(f"{base}/files/{file['id']}/export.docx")
    assert docx.status_code == 200
    with zipfile.ZipFile(io.BytesIO(docx.content)) as archive:
        body = archive.read("word/document.xml").decode()
        core = archive.read("docProps/core.xml").decode()
        everything = "".join(archive.read(name).decode("utf-8", "replace") for name in archive.namelist()
                             if name.endswith((".xml", ".rels")))
    # The title goes to the document title block and to the core properties; both must keep the accents.
    assert re.sub(r"<[^>]+>", "", body).startswith(title)
    assert f"<dc:title>{title}</dc:title>" in core
    assert "\ufffd" not in everything and "histÃ²ria" not in everything


def test_static_document_strips_scripts_handlers_and_external_resources():
    from educrea_api.services.render import static_document

    page = ('<html><head><link rel="stylesheet" href="s.css"><link rel="stylesheet" href="https://evil.test/a.css">'
            '<script>fetch("https://evil.test")</script></head><body onload="x()"><svg onclick="y()"><text>Hola</text></svg>'
            '<script src="a.js"></script><iframe src="https://evil.test"></iframe></body></html>')
    out = static_document(page, {"s.css": "svg{fill:red}"})
    assert "svg{fill:red}" in out and "Hola" in out
    for forbidden in ("<script", "onload", "onclick", "evil.test", "<iframe"):
        assert forbidden not in out
    assert "default-src 'none'" in out


def test_png_export_renders_html_in_sandbox(client: TestClient):
    import shutil
    import pytest

    if not (shutil.which("chromium") and shutil.which("bwrap")):
        pytest.skip("chromium/bwrap no disponibles")
    headers, base, _ = setup(client)
    page = client.post(f"{base}/files", headers=headers, json={
        "path": "info.html", "content": "<h1>Notas</h1><svg width='100' height='50'><rect width='100' height='50'/></svg>"}).json()
    response = client.get(f"{base}/files/{page['id']}/export.png?width=600&height=300")
    assert response.status_code == 200 and response.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert client.get(f"{base}/files/{page['id']}/export.png?width=99999").status_code == 422
    md = client.get(f"{base}/files").json()[0]
    assert client.get(f"{base}/files/{md['id']}/export.png").status_code == 422


def test_zip_includes_lucide_license_only_when_icons_are_used(client: TestClient):
    from pathlib import Path

    headers, base, _ = setup(client)

    def names():
        with zipfile.ZipFile(io.BytesIO(client.get(f"{base}/export.zip").content)) as archive:
            return archive.namelist(), archive
    assert "LICENSES/lucide-LICENSE.txt" not in names()[0]
    client.post(f"{base}/files", headers=headers, json={
        "path": "info.html", "content": '<!-- Icons: Lucide (ISC) --><svg class="lucide lucide-music"></svg>'})
    with zipfile.ZipFile(io.BytesIO(client.get(f"{base}/export.zip").content)) as archive:
        assert "LICENSES/lucide-LICENSE.txt" in archive.namelist()
        packaged = archive.read("LICENSES/lucide-LICENSE.txt")
    official = Path(__file__).resolve().parents[3] / "third_party" / "lucide" / "LICENSE"
    assert packaged == official.read_bytes()
