import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from educrea_api.main import app
from educrea_api.services.ai.providers.gemini import get_gemini_provider
from test_ai import StubGemini, setup_user
from test_auth_projects import register

FIXTURES = Path(__file__).parent / "fixtures"
PNG = (FIXTURES / "trompeta.png").read_bytes()
JPG = (FIXTURES / "sol.jpg").read_bytes()


def upload(client, base, headers, data, filename="Trompeta Dorada.png", alt="Una trompeta", credit="Dibujo propio"):
    return client.post(f"{base}/assets", headers={**headers, "Content-Type": "application/octet-stream"},
                       params={"filename": filename, "alt": alt, "credit": credit}, content=data)


def test_upload_validates_content_alt_limits_and_ownership(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    created = upload(client, base, headers, PNG)
    assert created.status_code == 201, created.text
    asset = created.json()
    assert asset["path"] == "imagenes/trompeta-dorada.png" and asset["media_type"] == "image/png"
    assert upload(client, base, headers, PNG, filename="otra.png").status_code == 409  # same bytes twice
    assert upload(client, base, headers, JPG, filename="trompeta-dorada.jpg").json()["path"] == "imagenes/trompeta-dorada.jpg"
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert upload(client, base, headers, svg, filename="x.svg").status_code == 422
    assert upload(client, base, headers, b"GIF89a....", filename="x.png").status_code == 422  # extension ignored
    assert upload(client, base, headers, PNG + b"x", alt=" ").status_code == 422
    assert upload(client, base, headers, b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024)).status_code == 413
    content = client.get(f"{base}/assets/{asset['id']}/content")
    assert content.content == PNG and content.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in content.headers["content-security-policy"]
    edited = client.patch(f"{base}/assets/{asset['id']}", headers=headers, json={"alt": "Trompeta azul", "credit": ""})
    assert edited.json()["alt"] == "Trompeta azul"
    assert client.post(f"{base}/assets", params={"filename": "a.png", "alt": "a"}, content=PNG).status_code == 403
    client.post("/api/auth/logout", headers=headers)
    other = {"X-CSRF-Token": register(client, "otra@example.org")}
    assert client.get(f"{base}/assets").status_code == 404
    assert client.get(f"{base}/assets/{asset['id']}/content").status_code == 404
    assert client.delete(f"{base}/assets/{asset['id']}", headers=other).status_code == 404


def test_images_are_embedded_in_reading_view_exports_and_known_to_the_ai(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    upload(client, base, headers, PNG, filename="trompeta.png")
    md = "# Instrumentos\n\n![Trompeta de la orquesta](imagenes/trompeta.png)\n\n![remota](https://example.org/x.png)\n"
    file = client.post(f"{base}/files", headers=headers, json={"path": "ficha.md", "content": md}).json()
    rendered = client.get(f"{base}/files/{file['id']}/render").json()["html"]
    assert '<img src="data:image/png;base64,' in rendered and 'alt="Trompeta de la orquesta"' in rendered
    assert "example.org" not in rendered and "remota" in rendered  # remote images are never loaded
    exported = client.get(f"{base}/files/{file['id']}/export.html").text
    assert "img-src data:" in exported and "data:image/png;base64," in exported
    assert "Créditos de las imágenes" in exported and "Dibujo propio" in exported
    archive = zipfile.ZipFile(io.BytesIO(client.get(f"{base}/export.zip").content))
    assert archive.read("imagenes/trompeta.png") == PNG
    assert "Una trompeta — Dibujo propio" in archive.read("imagenes/CREDITOS.txt").decode()

    captured = {}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)

    draft = {"summary": "Con imagen", "changes": [{"path": "index.html", "content": '<img src="imagenes/trompeta.png" alt="x">'}]}
    app.dependency_overrides[get_gemini_provider] = lambda: Capture(json.dumps(draft))
    client.post(f"{base}/ai/proposals", headers=headers, json={
        "instruction": "Añade la imagen de la trompeta", "model": "gemini-test-free", "automatic": True})
    assert "available_images" in captured["prompt"] and "imagenes/trompeta.png" in captured["prompt"]
    assert "base64" not in captured["prompt"]  # the model gets the path and description, never the bytes


@pytest.mark.skipif(not (shutil.which("pandoc") and shutil.which("bwrap") and shutil.which("xelatex")),
                    reason="pandoc/xelatex/bwrap not installed")
def test_docx_and_pdf_include_library_images_only(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    upload(client, base, headers, PNG, filename="trompeta.png")
    md = "# Ficha\n\n![Trompeta](./imagenes/trompeta.png)\n\n![Fuera](https://example.org/x.png)\n"
    file = client.post(f"{base}/files", headers=headers, json={"path": "ficha.md", "content": md}).json()
    docx = client.get(f"{base}/files/{file['id']}/export.docx")
    assert docx.status_code == 200, docx.text
    media = [name for name in zipfile.ZipFile(io.BytesIO(docx.content)).namelist() if name.startswith("word/media/")]
    assert len(media) == 1
    document_xml = zipfile.ZipFile(io.BytesIO(docx.content)).read("word/document.xml").decode()
    assert "Créditos de las imágenes" in document_xml and "Dibujo propio" in document_xml
    pdf = client.get(f"{base}/files/{file['id']}/export.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and b"/Image" in pdf.content


def test_embed_replaces_only_library_references():
    from types import SimpleNamespace
    from educrea_api.services.assets import embed

    asset = SimpleNamespace(path="imagenes/sol.jpg", media_type="image/jpeg", data=JPG)
    html = ('<img src="imagenes/sol.jpg"><img src=\'./imagenes/sol.jpg\'><div style="background:url(imagenes/sol.jpg)">'
            '<img src="imagenes/otra.png"><img src="https://example.org/imagenes/sol.jpg">')
    out = embed(html, [asset])
    assert out.count("data:image/jpeg;base64,") == 3
    assert 'src="imagenes/otra.png"' in out and "https://example.org/imagenes/sol.jpg" in out


def test_deleting_a_project_removes_everything_it_owns(client: TestClient):
    """SQLite must cascade like PostgreSQL: no orphan images, versions or files after deleting a project."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from conftest import engine
    from educrea_api.models import FileVersion, ProjectFile
    from educrea_api.models.entities import ProjectAsset

    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    created = client.post(f"{base}/files", headers=headers, json={"path": "index.html", "content": "<h1>Hola</h1>"})
    assert created.status_code == 201
    assert client.post(f"{base}/assets?filename=trompeta.png&alt=Trompeta", headers=headers,
                       content=PNG).status_code == 201
    assert client.delete(base, headers=headers).status_code == 204
    assert client.get(base).status_code == 404
    with Session(engine) as db:
        for model in (ProjectFile, FileVersion, ProjectAsset):
            assert db.scalar(select(func.count()).select_from(model)) == 0, model.__name__
