import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from edustudio_api.main import app
from edustudio_api.services import templates as service
from edustudio_api.services.ai.providers.gemini import get_gemini_provider
from edustudio_api.services.converter import _sandbox
from test_ai import StubGemini, setup_user

INTERACTIVE = [t.id for t in service.TEMPLATES.values() if t.kind == "interactiva"]
BROWSER = shutil.which("chromium") or shutil.which("chromium-browser")


def test_catalog_has_eight_bilingual_templates(client: TestClient):
    headers, _ = setup_user(client)
    items = client.get("/api/templates").json()
    assert len(items) == 8 and all(item["names"]["es"] and item["names"]["va"] for item in items)


@pytest.mark.parametrize("template_id", INTERACTIVE)
@pytest.mark.parametrize("language", ["es", "va"])
def test_samples_are_valid_for_their_schema(template_id, language):
    files = service.initial_files(template_id, {"title": "Prueba", "language": language})
    assert set(files) == {"index.html", "style.css", "comun.js", "script.js", "datos.js"}
    assert service.validate_data(template_id, files["datos.js"]) == []
    assert ('lang="ca"' if language == "va" else 'lang="es"') in files["index.html"]
    assert "innerHTML" not in files["script.js"] + files["comun.js"]


def test_validation_explains_the_problems():
    bad = service.data_js({"title": "X", "questions": [{"text": "¿?", "options": ["a", "b"], "answer": 5}]})
    assert any("answer" in problem for problem in service.validate_data("cuestionario", bad))
    assert service.validate_data("cuestionario", "const x = 1") != []
    assert service.validate_data("cuestionario", "window.EDUSTUDIO_DATA = {title: 'x'};")[0].startswith("el objeto")
    image = service.data_js({"title": "X", "cards": [{"front": "a", "back": "b", "image": "imagenes/a.png"}]})
    assert any("alt" in problem for problem in service.validate_data("tarjetas", image))
    remote = service.data_js({"title": "X", "cards": [{"front": "a", "back": "b", "image": "https://x.org/a.png", "alt": "a"}]})
    assert service.validate_data("tarjetas", remote) != []


def test_apply_template_only_on_empty_projects_and_first_version_fills_only_data(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    assert client.post(f"{base}/template", headers=headers, json={"template": "nope"}).status_code == 404
    applied = client.post(f"{base}/template", headers=headers, json={"template": "cuestionario", "brief": {
        "title": "Instruments", "language": "va", "level": "primaria", "instructions": "Cinc preguntes", "kind": "situacion"}})
    assert applied.status_code == 201, applied.text
    assert client.post(f"{base}/template", headers=headers, json={"template": "ficha"}).status_code == 409
    files = {f["path"]: f for f in client.get(f"{base}/files").json()}
    brief = json.loads(client.get(f"{base}/files/{files['activity.json']['id']}").json()["content"])
    assert brief["template"] == "cuestionario" and brief["kind"] == "actividad" and brief["language"] == "va"

    captured = {}
    data = service.data_js({"title": "Instruments", "language": "va", "labels": service.LABELS["va"], "questions": [
        {"text": "Quin és de corda?", "options": ["Violí", "Flauta"], "answer": 0}]})
    good = {"summary": "Preguntes", "changes": [{"path": "datos.js", "content": data}]}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)

    app.dependency_overrides[get_gemini_provider] = lambda: Capture(json.dumps(good))
    body = client.post(f"{base}/ai/from-brief", headers=headers).json()
    assert body["status"] == "applied" and body["grounding"]["template_problems"] == []
    assert "NO modifiques index.html" in captured["prompt"] and "valenciano" in captured["prompt"]
    assert "Crea index.html, style.css y script.js" not in captured["prompt"]

    # Engine changed or invalid data: never applied automatically, problems are explained.
    broken = {"summary": "Mal", "changes": [{"path": "script.js", "content": "alert(1)"},
                                             {"path": "datos.js", "content": "window.EDUSTUDIO_DATA = {\"title\": \"\"};"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(broken))
    pending = client.post(f"{base}/ai/from-brief", headers=headers).json()
    assert pending["status"] == "pending"
    problems = " ".join(pending["grounding"]["template_problems"])
    assert "motor" in problems and "title" in problems and "questions" in problems


def test_ficha_template_creates_markdown_with_sections(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    client.post(f"{base}/template", headers=headers, json={"template": "ficha", "brief": {"title": "Fraccions", "language": "va"}})
    files = {f["path"]: f for f in client.get(f"{base}/files").json()}
    content = client.get(f"{base}/files/{files['ficha.md']['id']}").json()["content"]
    assert content.startswith("# Fraccions") and "## Recorda" in content and "## Per a acabar: autoavaluació" in content


def inline(files: dict[str, str]) -> str:
    page = re.sub(r'<link rel="stylesheet" href="style.css">', "<style>" + files["style.css"] + "</style>", files["index.html"])
    for name in ("datos.js", "comun.js", "script.js"):
        page = page.replace(f'<script src="{name}"></script>', "<script>" + files[name] + "</script>")
    return page


@pytest.mark.skipif(not (BROWSER and shutil.which("bwrap")), reason="chromium/bwrap not installed")
@pytest.mark.parametrize("template_id,expected", [
    ("cuestionario", ["Comprobar", "Trompeta", 'type="radio"']), ("emparejar", ["<select", "Maúlla"]),
    ("ordenar", ["Subir", "Plantar la semilla"]), ("tarjetas", ['aria-pressed="false"', "Luna"]),
    ("clasificar", ["Seres vivos", "<select"]), ("lectura", ["Empezamos", "Continuar", "<details"])])
def test_engines_render_in_a_real_browser(template_id, expected):
    files = service.initial_files(template_id, {"title": "Prueba", "language": "es",
                                                "accessibility": {"large_text": True}})
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "page.html").write_text(inline(files), encoding="utf-8")
        command = [BROWSER, "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                   "--host-resolver-rules=MAP * ~NOTFOUND", "--virtual-time-budget=3000", "--dump-dom", "file:///work/page.html"]
        done = subprocess.run(_sandbox(work, command), capture_output=True, timeout=60, check=False)
    dom = done.stdout.decode()
    assert '<h1>Prueba</h1>' in dom and 'class="grande"' in dom, done.stderr.decode()[-500:]
    for text in expected:
        assert text in dom, text


def run_in_browser(page: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "page.html").write_text(page, encoding="utf-8")
        command = [BROWSER, "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
                   "--host-resolver-rules=MAP * ~NOTFOUND", "--virtual-time-budget=3000", "--dump-dom", "file:///work/page.html"]
        return subprocess.run(_sandbox(work, command), capture_output=True, timeout=60, check=False).stdout.decode()


@pytest.mark.skipif(not (BROWSER and shutil.which("bwrap")), reason="chromium/bwrap not installed")
@pytest.mark.parametrize("template_id,actions,expected", [
    ("cuestionario", "document.querySelector('input[value=\"1\"]').checked = true; document.querySelector('button.principal').click()",
     ["¡Correcto!", "1 de 1"]),
    ("emparejar", "document.querySelectorAll('select').forEach(function (s, i) { s.value = String(i) }); document.querySelector('button.principal').click()",
     ["3 de 3"]),
    ("tarjetas", "document.querySelector('.tarjeta').click()", ['aria-pressed="true"', "La estrella que nos da luz"]),
    ("lectura", "document.querySelector('button.principal').click()", ["Seguimos", "¡Has terminado!", "2 / 2"]),
])
def test_engines_respond_to_interaction(template_id, actions, expected):
    files = service.initial_files(template_id, {"title": "Prueba", "language": "es"})
    dom = run_in_browser(inline(files).replace("</body>", f"<script>{actions}</script></body>"))
    for text in expected:
        assert text in dom, text


@pytest.mark.skipif(not (BROWSER and shutil.which("bwrap")), reason="chromium/bwrap not installed")
def test_ordering_engine_checks_the_order():
    files = service.initial_files("ordenar", {"title": "Prueba", "language": "va"})
    # Sort by moving each step to its place with the real buttons, then check.
    solve = """
      var wanted = ['Plantar la llavor', 'Regar', 'Ix el brot', 'Creix la planta'];
      for (var pass = 0; pass < 10; pass++) {
        var rows = Array.from(document.querySelectorAll('ol li strong')).map(function (s) { return s.textContent.replace(/^\\d+\\. /, '') });
        for (var i = 1; i < rows.length; i++) {
          if (wanted.indexOf(rows[i]) < wanted.indexOf(rows[i - 1])) { document.querySelectorAll('ol li')[i].querySelector('button').click(); break }
        }
      }
      document.querySelector('button.principal').click()"""
    dom = run_in_browser(inline(files).replace("</body>", f"<script>{solve}</script></body>"))
    assert "Tot en ordre!" in dom and 'lang="ca"' in dom


def test_dua_on_a_template_project_adapts_the_data_and_validates_it(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    client.post(f"{base}/template", headers=headers, json={"template": "tarjetas", "brief": {"title": "Astres"}})
    measures = [{"principle": p, "barrier": "b", "measure": "m"} for p in ("representacion", "accion_expresion", "implicacion")]
    good_data = service.data_js({"title": "Astres", "cards": [{"front": "Sol", "back": "Estrella. Da luz."}]})
    draft = {"summary": "DUA", "changes": [{"path": "datos.js", "content": good_data}], "dua": {"barriers": [], "measures": measures}}
    captured = {}

    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)

    app.dependency_overrides[get_gemini_provider] = lambda: Capture(json.dumps(draft))
    body = client.post(f"{base}/ai/dua", headers=headers, json={"path": "datos.js", "auto_apply": True}).json()
    assert body["status"] == "applied" and body["grounding"]["template_problems"] == []
    assert "plantilla interactiva" in captured["prompt"]
    broken = {**draft, "changes": [{"path": "datos.js", "content": "window.EDUSTUDIO_DATA = {\"title\": \"A\", \"cards\": []};"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(broken))
    pending = client.post(f"{base}/ai/dua", headers=headers, json={"path": "datos.js", "auto_apply": True}).json()
    assert pending["status"] == "pending" and pending["grounding"]["template_problems"]
    assert client.post(f"{base}/ai/dua", headers=headers, json={"path": "script.js"}).status_code == 422
