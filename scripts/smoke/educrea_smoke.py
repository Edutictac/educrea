#!/usr/bin/env python3
"""End-to-end smoke test of an EduCrea installation with a real browser.

It walks the path a teacher follows: single sign-on, a new activity, generation with the included AI, a picture
from the free image bank, SCORM export (checked in Chromium against a mock LMS and, optionally, in a test Moodle) and
the resource bank (publish and withdraw, so nothing reaches the public catalogue). Everything it creates is deleted.

Configuration comes from the environment; no address, account or secret lives in the repository (see README.md).
Exit code 0 when every step passed or was skipped, 1 otherwise. On failure the command in EDUCREA_SMOKE_NOTIFY_CMD
receives the summary as its last argument.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

HERE = Path(__file__).resolve().parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def secret(command_var: str) -> str:
    """Run the command named in the variable and return its first output line (never printed)."""
    command = env(command_var)
    if not command:
        raise SkipStep(f"{command_var} sin configurar")
    result = subprocess.run(shlex.split(command), capture_output=True, text=True, check=True)
    return result.stdout.splitlines()[0].strip()


class SkipStep(Exception):
    pass


@dataclass
class Step:
    name: str
    status: str = "pending"
    detail: str = ""
    seconds: float = 0.0


@dataclass
class Run:
    base: str
    artifacts: Path
    steps: list[Step] = field(default_factory=list)
    state: dict = field(default_factory=dict)

    def step(self, name: str, func, *, needs: tuple[str, ...] = ()):
        step = Step(name)
        self.steps.append(step)
        started = time.monotonic()
        missing = [key for key in needs if key not in self.state]
        try:
            if missing:
                raise SkipStep("depende de un paso anterior que no se completó")
            detail = func()
            step.status, step.detail = "ok", detail or ""
        except SkipStep as exc:
            step.status, step.detail = "skip", str(exc)
        except Exception as exc:  # noqa: BLE001 - every failure is reported, the run continues
            step.status = "fail"
            step.detail = f"{exc.__class__.__name__}: {str(exc).splitlines()[0][:300] if str(exc) else ''}"
            (self.artifacts / f"{len(self.steps):02d}-traceback.txt").write_text(traceback.format_exc())
            page = self.state.get("page")
            if page is not None:
                try:
                    page.screenshot(path=str(self.artifacts / f"{len(self.steps):02d}-fallo.png"))
                except Exception:  # noqa: BLE001
                    pass
        step.seconds = round(time.monotonic() - started, 1)
        mark = {"ok": "OK  ", "skip": "SKIP", "fail": "FAIL"}[step.status]
        print(f"[{mark}] {name} ({step.seconds}s){' — ' + step.detail if step.detail else ''}", flush=True)

    @property
    def failed(self) -> list[Step]:
        return [step for step in self.steps if step.status == "fail"]


# ---------------------------------------------------------------- EduCrea helpers

def api(run: Run, method: str, path: str, **kwargs):
    ctx: BrowserContext = run.state["ctx"]
    headers = kwargs.pop("headers", {})
    if method != "GET":
        headers["X-CSRF-Token"] = run.state["csrf"]
    response = ctx.request.fetch(run.base + "/api" + path, method=method, headers=headers, timeout=300_000, **kwargs)
    return response


def expect(response, *codes: int):
    if response.status not in codes:
        body = response.text()[:300]
        raise AssertionError(f"{response.request.method if hasattr(response, 'request') else ''} "
                             f"{response.url} → {response.status}: {body}")
    return response


def sse_events(text: str) -> list[tuple[str, dict]]:
    events = []
    for chunk in text.split("\n\n"):
        name, data = "", ""
        for line in chunk.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data += line[6:]
        if name:
            events.append((name, json.loads(data) if data else {}))
    return events


# ---------------------------------------------------------------- steps

def check_public(run: Run):
    ctx: BrowserContext = run.state["ctx"]
    home = expect(ctx.request.get(run.base + "/"), 200)
    health = expect(ctx.request.get(run.base + "/api/health"), 200).json()
    legacy = env("EDUCREA_SMOKE_LEGACY_URL")
    extra = ""
    if legacy:
        response = ctx.request.get(legacy, max_redirects=0)
        location = response.headers.get("location", "")
        if response.status != 301 or not location.startswith(run.base):
            raise AssertionError(f"el dominio antiguo devuelve {response.status} → {location or '(sin destino)'}")
        extra = ", dominio antiguo 301"
    return f"portada {home.status}, salud {health.get('status', health)}{extra}"


def sso_login(run: Run):
    username = env("EDUCREA_SMOKE_USERNAME")
    if not username:
        raise SkipStep("EDUCREA_SMOKE_USERNAME sin configurar")
    password = secret("EDUCREA_SMOKE_PASSWORD_CMD")
    page: Page = run.state["ctx"].new_page()
    run.state["page"] = page
    page.goto(run.base + "/login", wait_until="networkidle")
    # Authentik: identification stage, then password stage (a hidden password field exists before it renders).
    page.locator("input[name=uidField]").fill(username)
    with page.expect_response(lambda r: "/flows/executor/" in r.url and r.request.method == "GET" and r.status == 200):
        page.keyboard.press("Enter")
    field_ = page.locator("ak-stage-password input[name=password]")
    field_.wait_for(state="visible")
    field_.fill(password)
    field_.press("Enter")
    page.wait_for_url(lambda url: url.startswith(run.base) and "/oidc/callback" not in url, timeout=45_000)
    page.wait_for_load_state("networkidle")
    me = expect(run.state["ctx"].request.get(run.base + "/api/auth/me"), 200).json()
    if me["user"].get("is_guest"):
        raise AssertionError("tras el SSO la sesión sigue siendo de visitante")
    run.state["csrf"] = me["csrf_token"]
    run.state["ai_authorized"] = bool(me["user"].get("included_ai_authorized"))
    run.state["user"] = me["user"]["id"]
    return f"sesión docente en {page.url.removeprefix(run.base) or '/'}"


def create_activity(run: Run):
    title = f"Prova automàtica {time.strftime('%Y-%m-%d %H:%M')}"
    project = expect(api(run, "POST", "/projects", data={"title": title, "description": "Smoke test; se borra solo."}),
                     201).json()
    run.state["project"] = project["id"]
    brief = {"title": "El cicle de l'aigua", "language": "va", "level": "5é de Primària",
             "instructions": "Batería breve sobre el ciclo del agua: evaporación, condensación y precipitación. "
                             "Dos preguntas de opción múltiple, dos de verdadero o falso y dos huecos.",
             "mix": ["choice", "true_false", "gap"], "gap_mode": "bank",
             "accessibility": {"large_text": False, "high_contrast": False}}
    expect(api(run, "POST", f"/projects/{project['id']}/template", data={"template": "bateria", "brief": brief}), 201)
    return f"proyecto {project['id'][:8]} con plantilla «bateria»"


def generate_with_ai(run: Run):
    if env("EDUCREA_SMOKE_SKIP_AI") == "1":
        raise SkipStep("desactivado con EDUCREA_SMOKE_SKIP_AI=1")
    if not run.state.get("ai_authorized"):
        raise SkipStep("la cuenta no tiene acceso a la IA EduCrea (actívalo en /admin/beta)")
    project = run.state["project"]
    response = expect(api(run, "POST", f"/projects/{project}/ai/from-brief/stream",
                          data={"provider": "educrea", "model": "included"}), 200)
    events = sse_events(response.text())
    errors = [data for name, data in events if name == "error"]
    if errors:
        raise AssertionError(f"la IA devolvió error: {errors[0].get('message') or errors[0]}")
    proposals = [data for name, data in events if name == "proposal"]
    if not proposals:
        raise AssertionError(f"la generación terminó sin propuesta (eventos: {[n for n, _ in events][-5:]})")
    proposal = proposals[-1]
    if proposal.get("status") != "applied":
        raise AssertionError(f"propuesta en estado {proposal.get('status')}, no aplicada")
    run.state["generated"] = True
    stages = sorted({data.get("stage") for name, data in events if name == "status" and data.get("stage")})
    return f"propuesta aplicada ({len(proposal.get('changes') or [])} cambios; etapas: {', '.join(stages)})"


def file_content(run: Run, path: str) -> str | None:
    project = run.state["project"]
    listing = expect(api(run, "GET", f"/projects/{project}/files"), 200).json()
    match = next((item for item in listing if item.get("path") == path), None)
    if match is None:
        return None
    return expect(api(run, "GET", f"/projects/{project}/files/{match['id']}"), 200).json().get("content")


def adapt_dua(run: Run):
    """Adapt the generated activity for diversity (DUA), as the teacher panel does: interactive templates adapt
    datos.js. The SCORM steps that follow then check that the adapted activity still works and scores."""
    project = run.state["project"]
    previous = file_content(run, "datos.js")
    if previous is None:
        raise AssertionError("el proyecto no tiene datos.js que adaptar")
    response = expect(api(run, "POST", f"/projects/{project}/ai/dua/stream", data={
        "provider": "educrea", "model": "included", "path": "datos.js", "auto_apply": True,
        "needs": "Alumnado con TEA y con dislexia: frases cortas, vocabulario concreto y apoyo visual."}), 200)
    events = sse_events(response.text())
    errors = [data for name, data in events if name == "error"]
    if errors:
        raise AssertionError(f"la adaptación DUA devolvió error: {errors[0].get('message') or errors[0]}")
    proposals = [data for name, data in events if name == "proposal"]
    if not proposals:
        raise AssertionError(f"la adaptación terminó sin propuesta (eventos: {[n for n, _ in events][-5:]})")
    proposal = proposals[-1]
    if proposal.get("status") != "applied":
        raise AssertionError(f"propuesta DUA en estado {proposal.get('status')}, no aplicada")
    changed = [change.get("path") for change in proposal.get("changes") or []]
    if "datos.js" not in changed:
        raise AssertionError(f"la adaptación no modificó datos.js (cambios: {changed})")
    if file_content(run, "datos.js") == previous:
        raise AssertionError("datos.js no cambió tras aplicar la adaptación")
    return f"adaptación aplicada sobre datos.js ({len(changed)} cambio(s))"


def image_bank(run: Run):
    response = api(run, "GET", "/image-banks")
    if response.status == 404:
        raise SkipStep("el banco de imágenes libres aún no está desplegado en esta instalación")
    expect(response, 200)
    found = expect(api(run, "GET", "/image-banks/arasaac/search", params={"q": "agua", "language": "es"}), 200).json()
    if not found.get("items"):
        raise AssertionError("ARASAAC no devolvió resultados para «agua»")
    item = found["items"][0]
    thumb = expect(api(run, "GET", f"/image-banks/arasaac/{item['id']}/thumbnail"), 200)
    if not thumb.body().startswith(b"\x89PNG"):
        raise AssertionError("la miniatura no es un PNG")
    asset = expect(api(run, "POST", f"/projects/{run.state['project']}/assets/from-bank",
                       data={"provider": "arasaac", "id": item["id"], "alt": "Agua"}), 201).json()
    credit = asset.get("credit") or ""
    if "ARASAAC" not in credit.upper():
        raise AssertionError(f"la imagen importada no lleva el crédito de ARASAAC ({credit!r})")
    return f"{len(found['items'])} resultados; importado el pictograma {item['id']} con crédito"


def export_scorm(run: Run):
    response = expect(api(run, "GET", f"/projects/{run.state['project']}/export.scorm.zip"), 200)
    body = response.body()
    package = run.artifacts / "paquete-scorm.zip"
    package.write_bytes(body)
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        names = set(archive.namelist())
        for required in ("imsmanifest.xml", "index.html", "scorm.js", "datos.js"):
            if required not in names:
                raise AssertionError(f"falta {required} en el paquete")
        manifest = archive.read("imsmanifest.xml").decode()
        if "ADL SCORM" not in manifest or "1.2" not in manifest:
            raise AssertionError("imsmanifest.xml no declara SCORM 1.2")
        data = archive.read("datos.js").decode()
    if run.state.get("generated") and ("Sol" in data and "Luna" in data):
        raise AssertionError("datos.js conserva el ejemplo de la plantilla tras generar")
    run.state["scorm"] = package
    return f"{len(body) // 1024} KB, {len(names)} archivos, manifiesto SCORM 1.2"


ANSWER_JS = """
() => {
  const D = window.EDUCREA_DATA || {}; let answered = 0
  ;(D.blocks || []).forEach((block, b) => {
    if (block.type === 'choice') (block.questions || []).forEach((q, i) => {
      const input = document.querySelector(`input[name="b${b}-c${i}"][value="${q.answer}"]`); if (input) { input.checked = true; answered++ } })
    if (block.type === 'true_false') (block.statements || []).forEach((s, i) => {
      const input = document.querySelector(`input[name="b${b}-v${i}"][value="${String(s.answer)}"]`); if (input) { input.checked = true; answered++ } })
    if (block.type === 'gap') (block.items || []).forEach((item, i) => {
      const control = document.getElementById(`hueco-${b}-${i}`); if (control) { control.value = item.answers[0]; answered++ } })
  })
  return answered
}
"""

MOCK_LMS = """<!doctype html><meta charset="utf-8"><title>LMS simulado</title>
<script>
window.lms = { calls: [], values: {} }
window.API = {
  LMSInitialize: () => { lms.calls.push('init'); return 'true' },
  LMSGetValue: k => lms.values[k] || '',
  LMSSetValue: (k, v) => { lms.values[k] = String(v); lms.calls.push('set ' + k); return 'true' },
  LMSCommit: () => { lms.calls.push('commit'); return 'true' },
  LMSFinish: () => { lms.calls.push('finish'); return 'true' },
  LMSGetLastError: () => '0', LMSGetErrorString: () => '', LMSGetDiagnostic: () => '' }
</script><iframe id="sco" src="index.html" style="width:100%;height:95vh;border:0"></iframe>"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102 - keep the report readable
        pass


def answer_battery(frame) -> int:
    answered = frame.evaluate(ANSWER_JS)
    if not answered:
        raise AssertionError("no se encontró ninguna pregunta que responder en la actividad")
    frame.get_by_role("button", name=re.compile("Comprobar|Comprova|Check", re.I)).first.click()
    return answered


def scorm_mock_lms(run: Run):
    folder = Path(tempfile.mkdtemp(prefix="educrea-scorm-"))
    try:
        with zipfile.ZipFile(run.state["scorm"]) as archive:
            archive.extractall(folder)
        (folder / "_lms.html").write_text(MOCK_LMS)
        handler = functools.partial(QuietHandler, directory=str(folder))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        page = run.state["ctx"].new_page()
        try:
            page.goto(f"http://127.0.0.1:{server.server_port}/_lms.html", wait_until="networkidle")
            frame = page.frame_locator("#sco")
            frame.locator("form").first.wait_for()
            answered = answer_battery(page.frame(url=re.compile(r"/index\.html")))
            page.wait_for_function("() => window.lms.values['cmi.core.score.raw'] !== undefined", timeout=10_000)
            values = page.evaluate("() => window.lms.values")
        finally:
            page.close()
            server.shutdown()
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if values.get("cmi.core.lesson_status") != "completed":
        raise AssertionError(f"estado SCORM {values.get('cmi.core.lesson_status')!r}, se esperaba completed")
    score = float(values["cmi.core.score.raw"])
    if score != 100:
        raise AssertionError(f"respondiendo bien se obtiene {score}, no 100")
    return f"{answered} respuestas correctas → nota 100 y completed"


def moodle_php(*args: str) -> dict:
    # Copy helper (and package, if any) to a world-readable temporary folder: the web server user runs them.
    folder = Path(tempfile.mkdtemp(prefix="educrea-moodle-"))
    folder.chmod(0o755)
    helper = folder / "moodle_scorm.php"
    shutil.copy(HERE / "moodle_scorm.php", helper)
    args = list(args)
    if args[0] == "create":
        package = folder / "package.zip"
        shutil.copy(args[2], package)
        args[2] = str(package)
    for item in folder.iterdir():
        item.chmod(0o644)
    command = shlex.split(env("EDUCREA_SMOKE_MOODLE_PHP_CMD", "php")) + [str(helper), *args]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if result.returncode != 0:
        raise AssertionError(f"moodle_scorm.php {args[0]}: {result.stderr.strip()[-300:]}")
    return json.loads(result.stdout.strip().splitlines()[-1])


def scorm_moodle(run: Run):
    url = env("EDUCREA_SMOKE_MOODLE_URL").rstrip("/")
    if not url:
        raise SkipStep("EDUCREA_SMOKE_MOODLE_URL sin configurar")
    username, course = env("EDUCREA_SMOKE_MOODLE_USERNAME"), env("EDUCREA_SMOKE_MOODLE_COURSE")
    password = secret("EDUCREA_SMOKE_MOODLE_PASSWORD_CMD")
    created = moodle_php("create", course, str(run.state["scorm"]))
    cmid = created["cmid"]
    try:
        browser = run.state["browser"]
        ctx = browser.new_context(locale="es-ES")
        page = ctx.new_page()
        try:
            page.goto(url + "/login/index.php")
            page.fill("#username", username)
            page.fill("#password", password)
            page.click("#loginbtn")
            page.wait_for_load_state("networkidle")
            if "/login/" in page.url:
                raise AssertionError("no se pudo entrar en Moodle con la cuenta de prueba")
            page.goto(f"{url}/mod/scorm/view.php?id={cmid}")
            page.locator("form#scormviewform [type=submit]").click()
            page.wait_for_url(re.compile(r"/mod/scorm/player\.php"))
            page.frame_locator("#scorm_object").locator("form").first.wait_for(timeout=30_000)
            answered = answer_battery(page.frame(url=re.compile(r"/pluginfile\.php/.+index\.html")))
            page.wait_for_timeout(3000)  # autocommit sends the values to the server
            page.goto(url + "/my/")  # leaving the player runs LMSFinish
        finally:
            ctx.close()
        tracks = moodle_php("tracks", str(cmid), username)
    finally:
        if env("EDUCREA_SMOKE_KEEP") != "1":
            moodle_php("delete", str(cmid))
    if tracks.get("score") != 100:
        raise AssertionError(f"Moodle registró nota {tracks.get('score')} (estado {tracks.get('status')}), se esperaba 100")
    return f"importado en Moodle, {answered} respuestas → nota 100 registrada ({tracks.get('status')})"


def banc(run: Run):
    if env("EDUCREA_SMOKE_BANC") != "1":
        raise SkipStep("desactivado (EDUCREA_SMOKE_BANC=1 para probar publicar y retirar)")
    project = run.state["project"]
    taxonomy = expect(api(run, "GET", "/banc/taxonomy"), 200).json()
    subject = "Ciencias Naturales" if "Ciencias Naturales" in taxonomy.get("areas", []) else taxonomy["areas"][0]
    stages = taxonomy.get("stages") or taxonomy.get("educational_stages") or ["Primaria"]
    stage = stages[0] if isinstance(stages[0], str) else stages[0].get("value", "Primaria")
    published = expect(api(run, "POST", f"/projects/{project}/banc", data={
        "author": "Prova automàtica EduCrea", "description": "Prueba automática; se retira al momento.",
        "subject": subject, "educational_stage": stage}), 200, 201, 202).json()
    if published.get("status") != "pending":
        raise AssertionError(f"tras publicar el estado es {published.get('status')!r}, se esperaba pending")
    returned = ""
    review_url, review_cmd = env("EDUCREA_SMOKE_BANC_REVIEW_URL"), env("EDUCREA_SMOKE_BANC_REVIEW_TOKEN_CMD")
    if review_url and review_cmd:
        token = secret("EDUCREA_SMOKE_BANC_REVIEW_TOKEN_CMD")
        ctx: BrowserContext = run.state["ctx"]
        auth = {"Authorization": f"Bearer {token}"}
        pending = expect(ctx.request.get(review_url + "/api/internal/educrea/reviews?status=pending", headers=auth),
                         200).json()["items"]
        mine = [item for item in pending if item.get("id") == published.get("id")]
        if not mine:
            raise AssertionError("la publicación no aparece en la cola de revisión")
        expect(ctx.request.post(review_url + f"/api/internal/educrea/reviews/{mine[0]['id']}",
                                headers={**auth, "If-Match": f"\"{mine[0]['revision']}\"",
                                         "Content-Type": "application/json"},
                                data=json.dumps({"decision": "return", "feedback": "Prueba automática."})), 200)
        returned = ", devuelta en revisión"
    withdrawn = api(run, "DELETE", f"/projects/{project}/banc")
    if withdrawn.status not in (200, 204, 409):
        expect(withdrawn, 200, 204)
    return f"publicada en revisión{returned} y retirada (nunca pública)"


def cleanup(run: Run):
    if env("EDUCREA_SMOKE_KEEP") == "1":
        raise SkipStep("EDUCREA_SMOKE_KEEP=1: se conserva el proyecto")
    expect(api(run, "DELETE", f"/projects/{run.state['project']}"), 204)
    return "proyecto de prueba borrado"


# ---------------------------------------------------------------- main

def notify(run: Run):
    command = env("EDUCREA_SMOKE_NOTIFY_CMD")
    if not command:
        return
    lines = [f"EduCrea smoke: {len(run.failed)} paso(s) fallido(s) en {run.base}"]
    lines += [f"- {step.name}: {step.detail}" for step in run.failed]
    subprocess.run(shlex.split(command) + ["\n".join(lines)], timeout=60, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default=env("EDUCREA_SMOKE_URL"))
    parser.add_argument("--artifacts", default=env("EDUCREA_SMOKE_ARTIFACTS", ""))
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    if not args.base_url:
        parser.error("indica --base-url o EDUCREA_SMOKE_URL")
    artifacts = Path(args.artifacts or tempfile.mkdtemp(prefix="educrea-smoke-"))
    artifacts.mkdir(parents=True, exist_ok=True)
    artifacts.chmod(0o700)
    run = Run(base=args.base_url.rstrip("/"), artifacts=artifacts)
    print(f"EduCrea smoke test → {run.base} (artefactos en {artifacts})", flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        run.state["browser"] = browser
        run.state["ctx"] = browser.new_context(locale="es-ES", accept_downloads=True)
        try:
            run.step("Portada y salud", lambda: check_public(run))
            run.step("Login SSO", lambda: sso_login(run))
            run.step("Crear actividad (batería)", lambda: create_activity(run), needs=("csrf",))
            run.step("Generar con IA EduCrea", lambda: generate_with_ai(run), needs=("project",))
            run.step("Adaptación DUA", lambda: adapt_dua(run), needs=("generated",))
            run.step("Banco de imágenes libres (ARASAAC)", lambda: image_bank(run), needs=("project",))
            run.step("Exportar SCORM", lambda: export_scorm(run), needs=("project",))
            run.step("SCORM en LMS simulado", lambda: scorm_mock_lms(run), needs=("scorm",))
            run.step("SCORM en Moodle de pruebas", lambda: scorm_moodle(run), needs=("scorm",))
            run.step("Banc: publicar y retirar", lambda: banc(run), needs=("project",))
        finally:
            run.step("Limpieza", lambda: cleanup(run), needs=("project",))
            browser.close()
    report = {"base": run.base, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "steps": [step.__dict__ for step in run.steps]}
    (artifacts / "informe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    ok = sum(step.status == "ok" for step in run.steps)
    skipped = sum(step.status == "skip" for step in run.steps)
    print(f"Resultado: {ok} OK, {skipped} omitidos, {len(run.failed)} fallidos", flush=True)
    if run.failed:
        notify(run)
        return 1
    return 0


def crash_guard() -> int:
    try:
        return main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - the browser or the configuration broke before any step ran
        traceback.print_exc()
        command = env("EDUCREA_SMOKE_NOTIFY_CMD")
        if command:
            subprocess.run(shlex.split(command) + [f"EduCrea smoke: el script falló antes de terminar ({exc.__class__.__name__}: {exc})"[:900]],
                           timeout=60, check=False)
        return 2


if __name__ == "__main__":
    sys.exit(crash_guard())
