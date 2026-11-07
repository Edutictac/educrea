import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from educrea_api.config import get_settings
from test_auth_projects import register

FIXTURES = str(Path(__file__).parent / "fixtures")


@pytest.fixture
def mcp_config(monkeypatch):
    if not shutil.which("bwrap"):
        pytest.skip("bwrap no disponible")
    config = {"notes": {"command": ["python3", f"{FIXTURES}/fake_mcp.py"], "ro_paths": [FIXTURES], "timeout": 10,
                        "tools": {"solfege": {"mutates": False}, "write": {"mutates": True}}}}
    monkeypatch.setattr(get_settings(), "mcp_servers_json", json.dumps(config))


def setup(client, email="c@example.org"):
    headers = {"X-CSRF-Token": register(client, email)}
    project = client.post("/api/projects", headers=headers, json={"title": "Música"}).json()
    base = f"/api/projects/{project['id']}"
    client.post(f"{base}/files", headers=headers, json={"path": "index.html", "content": "<h1>Do re mi</h1>\nfa sol"})
    return headers, base


def test_builtin_capabilities_are_typed_and_audited(client: TestClient):
    headers, base = setup(client)
    invoke = lambda name, args, **kw: client.post(f"{base}/capabilities/{name}/invoke", headers=headers,
                                                  json={"arguments": args, **kw})
    assert invoke("project.list_files", {}).json()["files"][0]["path"] == "index.html"
    assert "Do re mi" in invoke("project.read_file", {"path": "index.html"}).json()["content"]
    assert invoke("project.search", {"query": "SOL"}).json()["matches"][0]["line"] == 2
    assert invoke("project.read_file", {}).status_code == 422
    assert invoke("project.read_file", {"path": "x.js"}).status_code == 404
    assert invoke("project.nope", {}).status_code == 404
    audit = client.get(f"{base}/capabilities/audit").json()
    assert {row["status"] for row in audit} == {"ok", "error"}
    assert "Do re mi" not in json.dumps(audit)


def test_invoke_requires_csrf_and_ownership(client: TestClient):
    headers, base = setup(client)
    assert client.post(f"{base}/capabilities/project.list_files/invoke", json={}).status_code == 403
    client.post("/api/auth/logout", headers=headers)
    other = {"X-CSRF-Token": register(client, "o@example.org")}
    assert client.post(f"{base}/capabilities/project.list_files/invoke", headers=other, json={}).status_code == 404
    assert client.get(f"{base}/capabilities/audit").status_code == 404


def test_mcp_allowlist_schema_untrusted_and_approval(client: TestClient, mcp_config):
    headers, base = setup(client)
    names = {item["name"] for item in client.get("/api/capabilities").json()}
    assert "mcp.notes.solfege" in names and "mcp.notes.write" in names and "mcp.notes.hidden" not in names
    call = lambda name, args, **kw: client.post(f"{base}/capabilities/{name}/invoke", headers=headers,
                                                json={"arguments": args, **kw})
    ok = call("mcp.notes.solfege", {"note": "D"})
    assert ok.status_code == 200 and ok.json()["untrusted"] is True and "Re" in ok.json()["result"]
    assert call("mcp.notes.solfege", {"note": "Z"}).status_code == 422
    assert call("mcp.notes.solfege", {}).status_code == 422
    assert call("mcp.notes.hidden", {}).status_code == 404
    assert call("mcp.other.x", {}).status_code == 404
    assert call("mcp.notes.write", {}).status_code == 409
    assert call("mcp.notes.write", {}, approved=True).status_code == 200
    statuses = [row["status"] for row in client.get(f"{base}/capabilities/audit").json()]
    assert "denied" in statuses and "ok" in statuses


def test_agent_consults_read_only_capabilities_and_never_runs_mutating_ones(client: TestClient, mcp_config):
    from educrea_api.main import app
    from educrea_api.services.ai.providers.gemini import get_gemini_provider
    from test_ai import StubGemini, setup_user

    headers, project_id = setup_user(client)
    base = f"/api/projects/{project_id}"
    client.post(f"{base}/files", headers=headers, json={"path": "index.html", "content": "<h1>Notas</h1>"})
    consultation = {"summary": "consulta", "changes": [], "tool_calls": [
        {"name": "mcp.notes.solfege", "arguments_json": json.dumps({"note": "D"})},
        {"name": "mcp.notes.write", "arguments_json": "{}"},
        {"name": "project.read_file", "arguments_json": json.dumps({"path": "index.html"})},
        {"name": "mcp.notes.hidden", "arguments_json": "{}"},
        {"name": "project.search", "arguments_json": "no es json"}]}
    final = {"summary": "Con la nota", "changes": [{"path": "index.html", "content": "<h1>Re</h1>"}]}
    prompts: list[str] = []

    class Sequence(StubGemini):
        async def generate(self, key, model, prompt):
            prompts.append(prompt)
            self.text = json.dumps(consultation if len(prompts) == 1 else final)
            return await super().generate(key, model, prompt)

    app.dependency_overrides[get_gemini_provider] = lambda: Sequence("")
    body = client.post(f"{base}/ai/proposals", headers=headers, json={
        "instruction": "Usa la nota re del servidor de solfeo", "model": "gemini-test-free", "automatic": True})
    assert body.status_code == 201, body.text
    body = body.json()
    assert len(prompts) == 2 and "PASO DE CONSULTA" in prompts[0] and "mcp.notes.solfege" in prompts[0]
    assert "RESULTADOS DE LAS CAPACIDADES" in prompts[1] and "Re" in prompts[1] and "PASO DE CONSULTA" not in prompts[1]
    assert [step["status"] for step in body["agent_trace"]] == ["ok", "needs_approval", "ok", "error", "error"]
    audit = client.get(f"{base}/capabilities/audit").json()
    assert not any(row["capability"] == "mcp.notes.write" for row in audit)  # never run, not even attempted
    assert {row["capability"] for row in audit} >= {"mcp.notes.solfege", "project.read_file"}
    # The teacher approves the pending one explicitly.
    approved = client.post(f"{base}/capabilities/mcp.notes.write/invoke", headers=headers,
                           json={"arguments": {}, "approved": True})
    assert approved.status_code == 200


def test_no_consultation_when_everything_fits_and_no_mcp(client: TestClient):
    from educrea_api.main import app
    from educrea_api.services.ai.providers.gemini import get_gemini_provider
    from test_ai import StubGemini, setup_user

    headers, project_id = setup_user(client)
    calls = []

    class Count(StubGemini):
        async def generate(self, key, model, prompt):
            calls.append(prompt)
            return await super().generate(key, model, prompt)

    draft = {"summary": "Uno", "changes": [{"path": "index.html", "content": "<h1>1</h1>"}]}
    app.dependency_overrides[get_gemini_provider] = lambda: Count(json.dumps(draft))
    body = client.post(f"/api/projects/{project_id}/ai/proposals", headers=headers, json={
        "instruction": "Crea una página sencilla", "model": "gemini-test-free", "automatic": True}).json()
    assert len(calls) == 1 and body["agent_trace"] is None
