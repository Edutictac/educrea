import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from edustudio_api.config import get_settings
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
