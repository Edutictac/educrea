import json
import re

from fastapi.testclient import TestClient

from educrea_api.main import app
from educrea_api.services.ai import sections as section_service
from educrea_api.services.ai.engine import SITUATION_SECTIONS
from educrea_api.services.ai.providers.base import ProviderChunk, ProviderError
from educrea_api.services.ai.providers.gemini import get_gemini_provider
from test_ai import setup_user, stream_events


class PerSection:
    """Fake AI that writes a recognisable body for the section named in the prompt."""

    def __init__(self, fail: str | None = None, quote: str | None = None):
        self.fail, self.quote, self.prompts = fail, quote, []

    async def stream(self, _key, _model, prompt):
        self.prompts.append(prompt)
        section = re.search(r"escribe SOLO la sección «([^»]+)»", prompt).group(1)
        if section == self.fail:
            raise ProviderError("error del proveedor", 400)
        body = f"## {section}\n\nTexto desarrollado de {section}. " + "Detalle del aula. " * 8
        draft = {"summary": "ok", "changes": [{"path": "seccion.md", "content": body}],
                 **({"citations": [{"chunk": "F1", "quote": self.quote}]} if self.quote else {})}
        yield ProviderChunk(text=json.dumps(draft, ensure_ascii=False), usage={"input_tokens": 5, "output_tokens": 50})


def situation(client, language="es", content="# Las notas\n\n## Evaluación\n\nCorta.\n\n## Saberes básicos\n\nTexto previo que se conserva.\n"):
    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    client.post(f"{base}/files", headers=headers, json={"path": "activity.json", "content": json.dumps(
        {"kind": "situacion", "title": "Las notas", "language": language, "level": "primaria"})})
    if content:
        client.post(f"{base}/files", headers=headers, json={"path": "situacion.md", "content": content})
    return headers, base


def read_document(client, base):
    row = next(f for f in client.get(f"{base}/files").json() if f["path"] == "situacion.md")
    return client.get(f"{base}/files/{row['id']}").json()["content"]


def test_whole_situation_is_written_section_by_section(client: TestClient):
    headers, base = situation(client, language="va", content="")
    fake = PerSection()
    app.dependency_overrides[get_gemini_provider] = lambda: fake
    events = stream_events(client.post(f"{base}/ai/sections/stream", headers=headers, json={}))
    statuses = [data for name, data in events if name == "status"]
    assert [s["index"] for s in statuses] == list(range(1, 10)) and statuses[0]["total"] == 9
    assert statuses[7]["section"] == "Atenció a la diversitat (DUA)"
    assert len([1 for name, _ in events if name == "section"]) == 9
    proposal = events[-1][1]
    assert events[-1][0] == "proposal" and proposal["status"] == "applied"
    assert proposal["grounding"]["sections_missing"] == []
    document = read_document(client, base)
    assert document.startswith("# Las notas") and document.count("\n## ") == 9
    assert document.count("Texto desarrollado de Avaluació") == 1  # the repeated heading was removed
    # Each later section sees the sections already written (coherence).
    assert "Texto desarrollado de Dades de la situació" in fake.prompts[-1]


def test_only_the_chosen_section_is_developed_and_the_rest_is_kept(client: TestClient):
    headers, base = situation(client)
    fake = PerSection()
    app.dependency_overrides[get_gemini_provider] = lambda: fake
    events = stream_events(client.post(f"{base}/ai/sections/stream", headers=headers, json={
        "sections": ["Evaluación"], "request": "Añade una rúbrica más completa"}))
    assert len(fake.prompts) == 1 and "Añade una rúbrica más completa" in fake.prompts[0]
    document = read_document(client, base)
    assert "Texto desarrollado de Evaluación" in document and "Corta." not in document
    assert "Texto previo que se conserva." in document
    assert events[-1][1]["status"] == "applied"  # what the teacher asked for; undoable from the history
    assert document.count("\n## ") == 9  # the missing headings are added (empty) in the right order
    assert client.post(f"{base}/ai/sections/stream", headers=headers, json={"sections": ["Inventada"]}).status_code == 422


def test_a_failing_section_keeps_its_previous_text_and_waits_for_review(client: TestClient):
    headers, base = situation(client)
    app.dependency_overrides[get_gemini_provider] = lambda: PerSection(fail="Saberes básicos")
    proposal = stream_events(client.post(f"{base}/ai/sections/stream", headers=headers, json={}))[-1][1]
    assert proposal["status"] == "pending"
    assert "no se han podido redactar: Saberes básicos" in " ".join(proposal["grounding"]["template_problems"])
    after = proposal["changes"][0]["after_content"]
    assert "Texto previo que se conserva." in after and "Texto desarrollado de Evaluación" in after


def test_sections_are_grounded_in_the_teachers_material(client: TestClient):
    headers, base = situation(client, content="")
    client.post(f"{base}/sources", headers={**headers, "Content-Type": "application/octet-stream"},
                params={"filename": "curriculo.md", "title": "Currículo"},
                content="# Música\n\nInterpretar canciones sencillas con la voz y con instrumentos de percusión.".encode())
    fake = PerSection(quote="Interpretar canciones sencillas con la voz y con instrumentos de percusión")
    app.dependency_overrides[get_gemini_provider] = lambda: fake
    proposal = stream_events(client.post(f"{base}/ai/sections/stream", headers=headers, json={}))[-1][1]
    assert "FUENTES DE REFERENCIA" in fake.prompts[0] and "instrumentos de percusión" in fake.prompts[0]
    assert proposal["grounding"]["verified"] >= 1 and proposal["grounding"]["unverified"] == 0
    assert proposal["status"] == "applied"


def test_split_and_join_keep_order_and_tolerate_translated_headings():
    preamble, parts = section_service.split("# T\n\nIntro\n\n## Avaluació\n\nA\n\n### Rúbrica\n\nR\n\n## Dades de la situació\n\nD\n")
    assert preamble == "# T\n\nIntro" and parts["Evaluación"].startswith("A") and "### Rúbrica" in parts["Evaluación"]
    joined = section_service.join("T", preamble, parts, "es")
    assert joined.index("## Datos de la situación") < joined.index("## Evaluación") and joined.count("\n## ") == len(SITUATION_SECTIONS)
