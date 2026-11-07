import json
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from educrea_api.main import app
from educrea_api.services import sources as service
from educrea_api.services.ai.providers import registry
from educrea_api.services.ai.providers.gemini import get_gemini_provider
from test_ai import StubGemini, setup_user

CURRICULUM = """# Currículo de Educación Primaria

Artículo 7. Competencia matemática

La competencia matemática implica comprender y resolver problemas. El alumnado de cuarto curso comparará fracciones
con el mismo denominador y las representará en la recta numérica.

Área de Educación Musical

Las notas musicales do re mi fa sol la si se escriben en el pentagrama. El alumnado reconocerá la clave de sol.

Área de Educació Física

L'alumnat practicarà jocs cooperatius i desenvoluparà la coordinació motriu.
""" + "\n\n".join(f"Área de Ciencias {n}\n\nTexto de relleno sobre el medio natural número {n}. " * 3 for n in range(60))


def upload(client, headers, base, name, data, title=""):
    return client.post(f"{base}/sources", params={"filename": name, "title": title}, content=data,
                       headers={**headers, "Content-Type": "application/octet-stream"})


def project(client):
    headers, project_id = setup_user(client)
    return headers, f"/api/projects/{project_id}", project_id


def test_chunking_keeps_headings_and_retrieval_finds_the_right_passage(client: TestClient):
    chunks = service.chunk_pages([(3, CURRICULUM)])
    assert len(chunks) > 10 and all(len(c["text"]) <= service.CHUNK_MAX + 200 for c in chunks)
    assert any(c["heading"].endswith("Área de Educación Musical") and "Currículo de Educación Primaria" in c["heading"] for c in chunks)
    headers, base, _ = project(client)
    assert upload(client, headers, base, "curriculo.md", CURRICULUM.encode()).status_code == 201
    source = client.get(f"{base}/sources").json()[0]
    found = client.get(f"{base}/sources/{source['id']}/search", params={"q": "actividad de notas musicales y pentagrama"}).json()
    assert found and "pentagrama" in found[0]["text"]
    fractions = client.get(f"{base}/sources/{source['id']}/search", params={"q": "Fracciones en cuarto de primaria"}).json()
    assert "fracciones" in fractions[0]["text"].lower()
    catalan = client.get(f"{base}/sources/{source['id']}/search", params={"q": "jocs cooperatius i coordinació"}).json()
    assert "cooperatius" in catalan[0]["text"]
    assert client.get(f"{base}/sources/{source['id']}/search", params={"q": "astrofísica cuántica"}).json() == []


def test_upload_limits_formats_isolation_and_delete(client: TestClient):
    headers, base, _ = project(client)
    assert upload(client, headers, base, "virus.exe", b"x").status_code == 422
    assert upload(client, headers, base, "vacio.txt", b"   ").status_code == 422
    assert client.post(f"{base}/sources", params={"filename": "a.txt"}, content=b"hola mundo largo").status_code == 403  # CSRF
    for n in range(service.MAX_SOURCES):
        assert upload(client, headers, base, f"s{n}.txt", f"Contenido útil número {n} con bastante texto".encode()).status_code == 201
    assert upload(client, headers, base, "extra.txt", b"otro documento").status_code == 409
    listed = client.get(f"{base}/sources").json()
    client.post("/api/auth/logout", headers=headers)
    from test_auth_projects import register
    other = {"X-CSRF-Token": register(client, "other@example.org")}
    assert client.get(f"{base}/sources").status_code == 404
    assert client.delete(f"{base}/sources/{listed[0]['id']}", headers=other).status_code == 404
    assert client.get(f"{base}/sources/{listed[0]['id']}/search", params={"q": "contenido"}).status_code == 404


@pytest.mark.skipif(not (shutil.which("pdftotext") and shutil.which("pandoc") and shutil.which("bwrap")),
                    reason="herramientas de conversión no disponibles")
def test_docx_and_pdf_extraction_run_in_sandbox(client: TestClient, tmp_path):
    headers, base, _ = project(client)
    md = tmp_path / "c.md"
    md.write_text(CURRICULUM, encoding="utf-8")
    docx = tmp_path / "c.docx"
    subprocess.run(["pandoc", str(md), "-o", str(docx)], check=True)
    assert upload(client, headers, base, "curriculo.docx", docx.read_bytes()).status_code == 201
    odt = tmp_path / "c.odt"
    subprocess.run(["pandoc", str(md), "-o", str(odt)], check=True)
    created = upload(client, headers, base, "curriculo.odt", odt.read_bytes(), title="Primaria ODT")
    assert created.status_code == 201 and created.json()["title"] == "Primaria ODT"
    assert upload(client, headers, base, "roto.docx", b"no es un docx").status_code == 422
    if shutil.which("xelatex"):
        pdf = tmp_path / "c.pdf"
        subprocess.run(["pandoc", str(md), "-o", str(pdf), "--pdf-engine=xelatex", "-V", "mainfont=DejaVu Serif"], check=True)
        result = upload(client, headers, base, "curriculo.pdf", pdf.read_bytes())
        assert result.status_code == 201 and result.json()["pages"] >= 1


def grounded_request(project_id, source_ids, **extra):
    return {"instruction": "Crea una actividad para aprender las notas musicales", "model": "gemini-test-free",
            "automatic": True, "auto_apply": True, "source_ids": source_ids, **extra}


def test_grounded_generation_verifies_citations_and_blocks_unsupported_auto_apply(client: TestClient, monkeypatch):
    headers, base, project_id = project(client)
    upload(client, headers, base, "curriculo.md", CURRICULUM.encode(), title="Currículo Primaria")
    source_id = client.get(f"{base}/sources").json()[0]["id"]
    seen = {}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            seen["prompt"] = prompt
            return await super().generate(key, model, prompt)

    route = f"{base}/ai/proposals"
    good = {"summary": "Actividad de notas", "changes": [{"path": "index.html", "content": "<h1>Notas</h1>"}],
            "citations": [{"chunk": "F1", "quote": "Las notas musicales do re mi fa sol la si se escriben en el pentagrama",
                           "used_for": "teoría"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: Capture(json.dumps(good))
    ok = client.post(route, headers=headers, json=grounded_request(project_id, [source_id]))
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["status"] == "applied" and body["grounding"]["supported"] is True
    assert body["grounding"]["citations"][0]["verified"] is True and body["grounding"]["sources"] == ["Currículo Primaria"]
    assert "FUENTES DE REFERENCIA" in seen["prompt"] and "pentagrama" in seen["prompt"] and "EXCLUSIVAMENTE" in seen["prompt"]
    assert "relleno sobre el medio natural número 1" not in seen["prompt"]  # only relevant passages are sent

    invented = {**good, "changes": [{"path": "index.html", "content": "<h1>Inventado</h1>"}],
                "citations": [{"quote": "Los alumnos deben tocar la guitarra eléctrica durante tres horas diarias"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(invented))
    bad = client.post(route, headers=headers, json=grounded_request(project_id, [source_id])).json()
    assert bad["status"] == "pending" and bad["grounding"]["supported"] is False and bad["grounding"]["unverified"] == 1
    index = next(f for f in client.get(f"{base}/files").json() if f["path"] == "index.html")
    assert client.get(f"{base}/files/{index['id']}").json()["content"] == "<h1>Notas</h1>"  # not applied

    none = {**good, "citations": []}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(none))
    assert client.post(route, headers=headers, json=grounded_request(project_id, [source_id])).json()["status"] == "pending"
    assert client.post(route, headers=headers, json=grounded_request(project_id, ["00000000-0000-0000-0000-000000000000"])).status_code == 422


def test_quote_verification_ignores_case_accents_and_spacing(client: TestClient):
    from conftest import engine as test_engine
    from sqlalchemy.orm import Session

    headers, base, project_id = project(client)
    upload(client, headers, base, "c.md", CURRICULUM.encode())
    source_id = client.get(f"{base}/sources").json()[0]["id"]
    from uuid import UUID
    with Session(test_engine) as db:
        checks = service.verify_quotes(db, UUID(project_id), [UUID(source_id)], [
            "LAS NOTAS   musicales do re mi fa sol la si SE ESCRIBEN en el pentagrama",
            "comparara fracciones con el mismo denominador",
            "corta", "texto que no aparece en ningún sitio del documento"])
    assert [c["verified"] for c in checks] == [True, True, False, False]


@pytest.mark.skipif(not service.ocr_available(), reason="pdftoppm/tesseract/bwrap not installed")
def test_scanned_pdf_is_read_with_ocr_in_sandbox():
    from pathlib import Path

    data = (Path(__file__).parent / "fixtures" / "escaneado.pdf").read_bytes()
    pages = service.extract("escaneado.pdf", data)
    assert pages[0][0] == 1
    text = service.norm(pages[0][1])
    for expected in ("competencias especificas", "instrumentos", "criterios de evaluacion"):
        assert expected in text, expected


def test_scanned_pdf_without_ocr_tools_gives_a_clear_error(monkeypatch):
    monkeypatch.setattr(service, "ocr_available", lambda: False)
    with pytest.raises(Exception) as caught:
        service.ocr_pdf(b"%PDF-1.4")
    assert caught.value.status_code == 422 and "OCR" in caught.value.detail


def test_first_version_is_created_from_the_teachers_material(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    client.post(f"{base}/template", headers=headers, json={"template": "cuestionario", "brief": {
        "title": "El ciclo del agua", "instructions": "x" * 9000}})
    material = ("# El ciclo del agua\n\nEl agua se evapora con el calor del sol y forma nubes.\n\n"
                "## Condensación\n\nEl vapor se enfría en el cielo y se convierte en gotas.\n")
    source = client.post(f"{base}/sources", headers={**headers, "Content-Type": "application/octet-stream"},
                         params={"filename": "apuntes.md", "title": "Mis apuntes"}, content=material.encode())
    assert source.status_code == 201, source.text
    captured = {}
    data = ("window.EDUCREA_DATA = " + json.dumps({"title": "El ciclo del agua", "questions": [
        {"text": "¿Qué forma el vapor al enfriarse?", "options": ["Gotas", "Piedras"], "answer": 0}]}) + ";")
    draft = {"summary": "Cuestionario", "changes": [{"path": "datos.js", "content": data}],
             "citations": [{"chunk": "F2", "quote": "El vapor se enfría en el cielo y se convierte en gotas"}]}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)

    app.dependency_overrides[get_gemini_provider] = lambda: Capture(json.dumps(draft))
    response = client.post(f"{base}/ai/from-brief", headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    prompt = captured["prompt"]
    # The whole (small) material reaches the model, in order, with the material rules; the brief is not cut.
    assert "MATERIAL DE PARTIDA" in prompt and "se evapora con el calor" in prompt and "se convierte en gotas" in prompt
    assert prompt.index("se evapora") < prompt.index("se convierte en gotas") and "x" * 9000 in prompt
    assert body["grounding"]["verified"] == 1 and body["grounding"]["template_problems"] == []
    assert body["status"] == "applied"
    # An invented quote is not applied automatically.
    invented = {**draft, "citations": [{"chunk": "F1", "quote": "El agua del mar es dulce y se bebe sin problema"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(invented))
    assert client.post(f"{base}/ai/from-brief", headers=headers).json()["status"] == "pending"
