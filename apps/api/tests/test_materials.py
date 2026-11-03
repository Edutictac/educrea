import io
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
