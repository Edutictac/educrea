import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from educrea_api.main import app
from educrea_api.services import templates as service
from educrea_api.services.ai.providers.gemini import get_gemini_provider
from educrea_api.services.converter import _sandbox
from test_ai import StubGemini, setup_user

INTERACTIVE = [t.id for t in service.TEMPLATES.values() if t.kind == "interactiva"]
BROWSER = shutil.which("chromium") or shutil.which("chromium-browser")


def test_catalog_has_fourteen_templates_in_four_languages(client: TestClient):
    headers, _ = setup_user(client)
    items = client.get("/api/templates").json()
    assert len(items) == 14 and all(item["names"]["es"] and item["names"]["ca"] and item["names"]["va"] and item["names"]["en"] for item in items)
    assert {item["group"] for item in items} == {"quick", "games", "reading", "docs"}


@pytest.mark.parametrize("template_id", INTERACTIVE)
@pytest.mark.parametrize("language", ["es", "ca", "va", "en"])
def test_samples_are_valid_for_their_schema(template_id, language):
    files = service.initial_files(template_id, {"title": "Prueba", "language": language})
    assert set(files) == {"index.html", "style.css", "comun.js", "script.js", "datos.js"}
    assert service.validate_data(template_id, files["datos.js"]) == []
    assert ('lang="ca-ES-valencia"' if language == "va" else f'lang="{language}"') in files["index.html"]
    assert "innerHTML" not in files["script.js"] + files["comun.js"]


def test_catalan_and_valencian_stay_distinct():
    catalan = service.initial_files("cuestionario", {"title": "Prova", "language": "ca"})
    valencian = service.initial_files("cuestionario", {"title": "Prova", "language": "va"})
    assert 'lang="ca"' in catalan["index.html"] and 'lang="ca-ES-valencia"' in valencian["index.html"]
    assert json.loads(re.search(r"= (\{.*\});", catalan["datos.js"], re.S).group(1))["labels"]["check"] == "Comprova"
    assert "catalán" in service.instruction("ficha", {"language": "ca"}, "Base")
    assert service.FICHA["ca"][0] == "Objectiu"


def test_validation_explains_the_problems():
    bad = service.data_js({"title": "X", "questions": [{"text": "¿?", "options": ["a", "b"], "answer": 5}]})
    assert any("answer" in problem for problem in service.validate_data("cuestionario", bad))
    assert service.validate_data("cuestionario", "const x = 1") != []
    assert service.validate_data("cuestionario", "window.EDUCREA_DATA = {title: 'x'};")[0].startswith("el objeto")
    image = service.data_js({"title": "X", "cards": [{"front": "a", "back": "b", "image": "imagenes/a.png"}]})
    assert any("alt" in problem for problem in service.validate_data("tarjetas", image))
    remote = service.data_js({"title": "X", "cards": [{"front": "a", "back": "b", "image": "https://x.org/a.png", "alt": "a"}]})
    assert service.validate_data("tarjetas", remote) != []


@pytest.mark.parametrize("item", [
    {"text": "Sin hueco", "answers": ["a"]},
    {"text": "___ y ___", "answers": ["a"]},
    {"text": "____", "answers": ["a"]},
    {"text": "Un ___", "answers": []},
    {"text": "Un ___", "answers": ["   "]},
    {"text": "Un ___", "answers": ["a" * 121]},
])
def test_gaps_reject_ambiguous_or_unsolvable_items(item):
    assert service.validate_data("huecos", service.data_js({"title": "X", "items": [item]}))


@pytest.mark.parametrize("answer", ["false", "true", 0, 1, None])
def test_true_false_rejects_answers_that_are_not_json_booleans(answer):
    data = {"title": "X", "statements": [{"text": "El Sol es una estrella.", "answer": answer, "feedback": "Emite luz."}]}
    assert service.validate_data("verdadero_falso", service.data_js(data))


def test_battery_accepts_the_three_block_types_and_rejects_invalid_data():
    good = {"title": "X", "blocks": [
        {"type": "choice", "heading": "Elige", "questions": [
            {"text": "¿?", "options": ["a", "b"], "answer": 0, "feedback": "f"}]},
        {"type": "true_false", "heading": "V/F", "statements": [
            {"text": "A", "answer": True, "feedback": "f"}]},
        {"type": "gap", "heading": "Huecos", "mode": "text", "items": [
            {"text": "Un ___", "answers": ["a"], "feedback": "f"}]}]}
    assert service.validate_data("bateria", service.data_js(good)) == []
    duplicate = {**good, "blocks": [good["blocks"][0], {**good["blocks"][0]}]}
    assert any("repitas" in problem for problem in service.validate_data("bateria", service.data_js(duplicate)))
    assert service.validate_data("bateria", service.data_js({**good, "blocks": [{"type": "otro"}]}))
    gap = {"type": "gap", "items": [{"text": "Sin hueco", "answers": ["a"]}]}
    assert service.validate_data("bateria", service.data_js({**good, "blocks": [gap]}))
    statement = {"text": "A", "answer": "true", "feedback": "f"}
    assert service.validate_data("bateria", service.data_js({**good, "blocks": [
        {"type": "true_false", "statements": [statement]}]}))
    question = {"text": "¿?", "options": ["a", "b"], "answer": 0}
    assert any("30" in problem for problem in service.validate_data("bateria", service.data_js({"title": "X", "blocks": [
        {"type": "choice", "questions": [question] * 11},
        {"type": "true_false", "statements": [{"text": "A", "answer": True, "feedback": "f"}] * 11},
        {"type": "gap", "items": [{"text": "___", "answers": ["a"]}] * 11}]})))


def test_battery_initial_files_respects_selected_types_and_gap_mode():
    files = service.initial_files("bateria", {"title": "X", "language": "va", "mix": ["choice", "gap"],
                                              "gap_mode": "text"})
    data = service.parse_data(files["datos.js"])
    assert [block["type"] for block in data["blocks"]] == ["choice", "gap"]
    assert data["blocks"][1]["mode"] == "text"
    assert service.validate_data("bateria", files["datos.js"]) == []


def test_battery_instruction_names_selected_blocks():
    text = service.instruction("bateria", {"language": "va", "mix": ["choice", "gap"], "gap_mode": "text"}, "Base")
    assert "Bloques elegidos: opción múltiple, completar huecos." in text
    assert "mode=text" in text


def test_battery_rejects_blocks_not_selected_by_the_teacher():
    data = service.initial_files("bateria", {"title": "X", "language": "es"})["datos.js"]
    report = service.check_proposal("bateria", [SimpleNamespace(path="datos.js", content=data)],
                                    brief={"mix": ["choice"]})
    problems = " ".join(report["template_problems"])
    assert "no elegidos" in problems and "true_false" in problems and "gap" in problems


def test_battery_creation_stores_mix_and_gap_mode(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    response = client.post(f"{base}/template", headers=headers, json={
        "template": "bateria", "brief": {"title": "Mix", "language": "va", "mix": ["choice", "true_false"],
                                         "gap_mode": "text"}})
    assert response.status_code == 201
    files = {f["path"]: f for f in client.get(f"{base}/files").json()}
    brief = json.loads(client.get(f"{base}/files/{files['activity.json']['id']}").json()["content"])
    assert brief["mix"] == ["choice", "true_false"] and brief["gap_mode"] == "text"
    data = service.parse_data(client.get(f"{base}/files/{files['datos.js']['id']}").json()["content"])
    assert [block["type"] for block in data["blocks"]] == ["choice", "true_false"]


def test_true_false_ai_requires_explanations_before_auto_applying(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    assert client.post(f"{base}/template", headers=headers, json={
        "template": "verdadero_falso", "brief": {"title": "Astres", "language": "va"}}).status_code == 201
    data = {"title": "Astres", "language": "va", "statements": [
        {"text": "La Lluna produeix llum.", "answer": False, "feedback": ""}]}
    def provider():
        return StubGemini(json.dumps({"summary": "Astres", "changes": [
            {"path": "datos.js", "content": service.data_js(data)}]}))
    app.dependency_overrides[get_gemini_provider] = provider
    pending = client.post(f"{base}/ai/from-brief", headers=headers).json()
    assert pending["status"] == "pending"
    assert any("feedback" in problem for problem in pending["grounding"]["template_problems"])
    data["statements"][0]["feedback"] = "La Lluna reflecteix la llum del Sol."
    body = client.post(f"{base}/ai/from-brief", headers=headers).json()
    assert body["status"] == "applied", body
    assert body["grounding"]["template_problems"] == []


@pytest.mark.skipif(not (BROWSER and shutil.which("bwrap")), reason="chromium/bwrap not installed")
@pytest.mark.parametrize("language", ["es", "ca", "va"])
def test_true_false_grades_false_and_empty_answers_and_resets(language):
    files = service.initial_files("verdadero_falso", {"title": "Prueba", "language": language})
    labels = service.LABELS[language]
    actions = """
      var check = document.querySelector('button.principal');
      var retry = document.querySelector('.acciones button:last-child');
      window.EduScorm = { score: function (n, total) { document.body.setAttribute('data-score', n + '/' + total) } };
      function expectScore(value) { if (document.body.getAttribute('data-score') !== value) throw Error('score ' + value) }
      check.click(); expectScore('0/2');
      if (!document.querySelector('fieldset p').textContent.includes(UNANSWERED)) throw Error('unanswered');
      document.querySelector('input[name=vf0][value=true]').click();
      document.querySelector('input[name=vf1][value=true]').click();
      check.click(); expectScore('1/2');
      if (!document.querySelectorAll('fieldset p')[1].textContent.includes(INCORRECT)) throw Error('incorrect');
      document.querySelector('input[name=vf1][value=false]').click();
      check.click(); expectScore('2/2');
      if (document.querySelectorAll('fieldset .bien').length !== 2) throw Error('feedback');
      if (!document.querySelector('input').labels.length) throw Error('label');
      retry.click();
      if (document.querySelector('input:checked') || document.querySelector('[aria-invalid]')) throw Error('reset');
      if (document.activeElement !== document.querySelector('input')) throw Error('focus');
      if (document.querySelector('.resultado').textContent || document.querySelector('fieldset p').textContent) throw Error('clear');
      document.body.setAttribute('data-tested', 'ok');
    """.replace('UNANSWERED', json.dumps(labels['unanswered'])).replace('INCORRECT', json.dumps(labels['incorrect']))
    dom = run_in_browser(inline(files).replace("</body>", f"<script>{actions}</script></body>"))
    assert 'data-tested="ok"' in dom
    assert labels['true'] in dom and labels['false'] in dom


@pytest.mark.parametrize("mode", ["bank", "text"])
def test_gaps_creation_and_ai_keep_the_chosen_mode(client: TestClient, mode):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    response = client.post(f"{base}/template", headers=headers, json={
        "template": "huecos", "brief": {"title": "Astres", "language": "va", "gap_mode": mode}})
    assert response.status_code == 201
    files = {f["path"]: f for f in client.get(f"{base}/files").json()}
    def content(path):
        return client.get(f"{base}/files/{files[path]['id']}").json()["content"]
    assert json.loads(content("activity.json"))["gap_mode"] == mode
    data = service.parse_data(content("datos.js"))
    assert data["mode"] == mode and data["language"] == "va"
    data["items"] = [{"text": "El Sol és una ___.", "answers": ["estrela", "estrella"]}]
    proposal = {"summary": "Astres", "changes": [{"path": "datos.js", "content": service.data_js(data)}]}
    captured = {}
    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured["prompt"] = prompt
            return await super().generate(key, model, prompt)
    app.dependency_overrides[get_gemini_provider] = lambda: Capture(json.dumps(proposal))
    body = client.post(f"{base}/ai/from-brief", headers=headers).json()
    assert body["status"] == "applied", body
    assert body["grounding"]["template_problems"] == []
    assert f"mode={mode}" in captured["prompt"] and "exactamente un hueco" in captured["prompt"]


@pytest.mark.skipif(not (BROWSER and shutil.which("bwrap")), reason="chromium/bwrap not installed")
@pytest.mark.parametrize("mode", ["bank", "text"])
@pytest.mark.parametrize("language", ["es", "ca", "va"])
def test_gaps_grade_alternatives_accents_retry_and_report_score(mode, language):
    files = service.initial_files("huecos", {"title": "Prueba", "language": language, "gap_mode": mode})
    data = service.parse_data(files["datos.js"])
    data["items"] = [
        {"text": "És un ___ natural.", "answers": ["satèl·lit", "satélite natural"], "feedback": "Orbita la Terra."},
        {"text": "Un ___ verd.", "answers": ["arbre"]},
        {"text": "Una ___ gran.", "answers": ["casa"]},
    ]
    files["datos.js"] = service.data_js(data)
    actions = """
      var controls = document.querySelectorAll('select, input[type=text]');
      var check = document.querySelector('button.principal');
      var retry = document.querySelector('.acciones button:last-child');
      window.EduScorm = { score: function (n, total) { document.body.setAttribute('data-score', n + '/' + total) } };
      check.click();
      if (document.body.getAttribute('data-score') !== '0/3') throw Error('empty');
      controls[0].value = MODE === 'bank' ? 'satèl·lit' : '  SATÉLITE   NATURAL  ';
      controls[1].value = 'arbre';
      controls[2].value = MODE === 'bank' ? 'arbre' : 'casá';
      check.click();
      if (document.body.getAttribute('data-score') !== '2/3') throw Error('grade');
      if (controls[2].getAttribute('aria-invalid') !== 'true') throw Error('invalid');
      if (!controls[0].labels.length || !controls[0].getAttribute('aria-describedby')) throw Error('label');
      if (!document.body.textContent.includes('Orbita la Terra.')) throw Error('feedback');
      retry.click();
      if (document.activeElement !== controls[0]) throw Error('focus');
      if (Array.from(controls).some(function (c) { return c.value || c.hasAttribute('aria-invalid') })) throw Error('reset');
      if (document.querySelector('.resultado').textContent) throw Error('result');
      document.body.setAttribute('data-tested', 'ok');
    """.replace('MODE', json.dumps(mode))
    dom = run_in_browser(inline(files).replace("</body>", f"<script>{actions}</script></body>"))
    assert 'data-tested="ok"' in dom
    assert ('lang="ca-ES-valencia"' if language == "va" else f'lang="{language}"') in dom


@pytest.mark.skipif(not (BROWSER and shutil.which("bwrap")), reason="chromium/bwrap not installed")
def test_battery_grades_all_block_types_and_resets():
    files = service.initial_files("bateria", {"title": "Prueba", "language": "es"})
    data = service.parse_data(files["datos.js"])
    data["blocks"] = [
        {"type": "choice", "heading": "Elige", "questions": [
            {"text": "P1", "options": ["A", "B"], "answer": 1, "feedback": "F1"}]},
        {"type": "true_false", "heading": "VF", "statements": [
            {"text": "S1", "answer": True, "feedback": "F2"},
            {"text": "S2", "answer": False, "feedback": "F3"}]},
        {"type": "gap", "heading": "Huecos", "mode": "text", "items": [
            {"text": "La ___ es azul.", "answers": ["estrella"], "feedback": "F4"}]}]
    files["datos.js"] = service.data_js(data)
    actions = """
      var check = document.querySelector('button.principal');
      var retry = document.querySelector('.acciones button:last-child');
      window.EduScorm = { score: function (n, total) { document.body.setAttribute('data-score', n + '/' + total) } };
      check.click();
      if (document.body.getAttribute('data-score') !== '0/4') throw Error('empty');
      if (!document.querySelector('fieldset p').textContent.includes(UNANSWERED)) throw Error('unanswered');
      document.querySelector('input[name="b0-c0"][value="1"]').click();
      document.querySelector('input[name="b1-v0"][value="true"]').click();
      document.querySelector('input[name="b1-v1"][value="false"]').click();
      document.querySelector('#hueco-2-0').value = 'estrella';
      check.click();
      if (document.body.getAttribute('data-score') !== '4/4') throw Error('grade');
      if (document.querySelectorAll('.bien').length !== 4) throw Error('feedback');
      retry.click();
      if (document.querySelector('input:checked') || document.querySelector('[aria-invalid]')) throw Error('reset');
      if (document.activeElement !== document.querySelector('input, select')) throw Error('focus');
      if (document.querySelector('.resultado').textContent) throw Error('result');
      document.body.setAttribute('data-tested', 'ok');
    """.replace('UNANSWERED', json.dumps(service.LABELS['es']['unanswered']))
    dom = run_in_browser(inline(files).replace("</body>", f"<script>{actions}</script></body>"))
    assert 'data-tested="ok"' in dom


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
                                             {"path": "datos.js", "content": "window.EDUCREA_DATA = {\"title\": \"\"};"}]}
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


def test_ficha_template_in_english(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    applied = client.post(f"{base}/template", headers=headers, json={
        "template": "ficha", "brief": {"title": "Fractions", "language": "en"}})
    assert applied.status_code == 201
    files = {f["path"]: f for f in client.get(f"{base}/files").json()}
    content = client.get(f"{base}/files/{files['ficha.md']['id']}").json()["content"]
    assert content.startswith("# Fractions") and "## Objective" in content and "## To finish: self-assessment" in content


def inline(files: dict[str, str]) -> str:
    page = re.sub(r'<link rel="stylesheet" href="style.css">', "<style>" + files["style.css"] + "</style>", files["index.html"])
    for name in ("datos.js", "comun.js", "script.js"):
        page = page.replace(f'<script src="{name}"></script>', "<script>" + files[name] + "</script>")
    return page


@pytest.mark.skipif(not (BROWSER and shutil.which("bwrap")), reason="chromium/bwrap not installed")
@pytest.mark.parametrize("template_id,expected", [
    ("cuestionario", ["Comprobar", "Trompeta", 'type="radio"']), ("emparejar", ["<select", "Maúlla"]),
    ("ordenar", ["Subir", "Plantar la semilla"]), ("tarjetas", ['aria-pressed="false"', "Luna"]),
    ("escucha", ["Añade un audio", 'type="radio"']),
    ("verdadero_falso", ["Verdadero", "Falso", 'value="false"']),
    ("huecos", ["Banco de palabras", "<select", "Hueco 1"]),
    ("bateria", ["Elige la respuesta", "Verdadero o falso", "Banco de palabras"]),
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
    ("emparejar", "var w = {'Perro': 'Ladra', 'Gato': 'Maúlla', 'Vaca': 'Muge'}; document.querySelectorAll('li.bloque').forEach(function (li) { li.querySelector('select').value = w[li.querySelector('strong').textContent] }); document.querySelector('button.principal').click()",
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
    assert "Tot en ordre!" in dom and 'lang="ca-ES-valencia"' in dom


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
    broken = {**draft, "changes": [{"path": "datos.js", "content": "window.EDUCREA_DATA = {\"title\": \"A\", \"cards\": []};"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: StubGemini(json.dumps(broken))
    pending = client.post(f"{base}/ai/dua", headers=headers, json={"path": "datos.js", "auto_apply": True}).json()
    assert pending["status"] == "pending" and pending["grounding"]["template_problems"]
    assert client.post(f"{base}/ai/dua", headers=headers, json={"path": "script.js"}).status_code == 422


def test_match_accepts_shared_answers_and_grades_by_text():
    shared = service.data_js({"title": "Famílies", "pairs": [
        {"left": "Violí", "right": "Corda"}, {"left": "Violoncel", "right": "Corda"}, {"left": "Trompeta", "right": "Vent metall"}]})
    assert service.validate_data("emparejar", shared) == []
    single = service.data_js({"title": "X", "pairs": [{"left": "a", "right": "Igual"}, {"left": "b", "right": "Igual"}]})
    problems = service.validate_data("emparejar", single)
    assert problems and not problems[0].split(": ", 1)[1].startswith("Value error")
    if not (BROWSER and shutil.which("bwrap")):
        return
    files = service.initial_files("emparejar", {"title": "Famílies", "language": "va"})
    files["datos.js"] = shared
    answer = """var wanted = {'Violí': 'Corda', 'Violoncel': 'Corda', 'Trompeta': 'Vent metall'};
      document.querySelectorAll('li.bloque').forEach(function (li) { li.querySelector('select').value = wanted[li.querySelector('strong').textContent] });
      document.querySelector('button.principal').click()"""
    dom = run_in_browser(inline(files).replace("</body>", f"<script>{answer}</script></body>"))
    assert "3 de 3" in dom and dom.count('<option value="Corda">') == 3  # one «Corda» per select, not repeated


def test_engine_of_existing_projects_can_be_updated_and_keeps_data(client: TestClient):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    client.post(f"{base}/template", headers=headers, json={"template": "emparejar", "brief": {"title": "Instruments"}})
    files = {f["path"]: f for f in client.get(f"{base}/files").json()}
    old = client.get(f"{base}/files/{files['script.js']['id']}").json()
    client.put(f"{base}/files/{old['id']}", headers=headers, json={"content": "// motor antiguo", "expected_version": old["version"]}).raise_for_status()
    data_before = client.get(f"{base}/files/{files['datos.js']['id']}").json()["content"]
    assert client.get(f"{base}/template").json() == {"template": "emparejar", "outdated": ["script.js"]}
    assert client.post(f"{base}/template/update", headers=headers).json()["updated"] == ["script.js"]
    assert client.get(f"{base}/template").json()["outdated"] == []
    assert "se corrige por el texto" in client.get(f"{base}/files/{files['script.js']['id']}").json()["content"]
    assert client.get(f"{base}/files/{files['datos.js']['id']}").json()["content"] == data_before
    assert client.post(f"{base}/template/update", headers=headers).json()["updated"] == []


@pytest.mark.parametrize("template_id", ["cuestionario", "huecos", "verdadero_falso", "bateria"])
def test_scorm_package_for_aules(client: TestClient, template_id):
    import io
    import xml.etree.ElementTree as ET
    import zipfile

    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    assert client.get(f"{base}/export.scorm.zip").status_code == 409  # no activity yet
    client.post(f"{base}/template", headers=headers, json={"template": template_id, "brief": {"title": "Instruments & veus"}})
    response = client.get(f"{base}/export.scorm.zip")
    assert response.status_code == 200 and "scorm" in response.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert {"imsmanifest.xml", "index.html", "scorm.js", "datos.js", "comun.js", "script.js", "style.css"} <= names
    assert "activity.json" not in names
    root = ET.fromstring(archive.read("imsmanifest.xml"))
    ns = {"c": "http://www.imsproject.org/xsd/imscp_rootv1p1p2"}
    assert root.find("c:metadata/c:schemaversion", ns).text == "1.2"
    assert root.find("c:organizations/c:organization/c:title", ns).text == "Instruments & veus"
    listed = {f.get("href") for f in root.findall("c:resources/c:resource/c:file", ns)}
    assert listed == names - {"imsmanifest.xml"}  # every file of the activity is declared
    index = archive.read("index.html").decode()
    assert index.index('src="scorm.js"') < index.index('src="datos.js"') and "EduScorm.complete" not in index


@pytest.mark.skipif(not (BROWSER and shutil.which("bwrap")), reason="chromium/bwrap not installed")
def test_scorm_bridge_reports_best_score_to_the_lms():
    from educrea_api.services import scorm

    files = service.initial_files("cuestionario", {"title": "Prova", "language": "va"})
    fake_lms = """<script>window.calls = []; window.API = {
      LMSInitialize: function () { calls.push('init'); return 'true' }, LMSGetValue: function () { return 'not attempted' },
      LMSSetValue: function (k, v) { calls.push(k + '=' + v); return 'true' }, LMSCommit: function () { return 'true' },
      LMSFinish: function () { return 'true' } }</script>"""
    page = inline(files).replace("<head>", "<head>" + fake_lms + "<script>" + scorm.SCORM_JS.read_text() + "</script>", 1)
    answer = """document.querySelector('button.principal').click();
      document.querySelector('input[value="1"]').checked = true; document.querySelector('button.principal').click();
      document.body.setAttribute('data-calls', JSON.stringify(window.calls))"""
    dom = run_in_browser(page.replace("</body>", f"<script>{answer}</script></body>"))
    calls = json.loads(re.search(r'data-calls="([^"]*)"', dom).group(1).replace("&quot;", '"'))
    assert calls[0] == "init" and "cmi.core.lesson_status=incomplete" in calls
    assert "cmi.core.score.raw=0" in calls and calls.count("cmi.core.score.raw=100") == 1  # best score reported
    assert "cmi.core.lesson_status=completed" in calls
