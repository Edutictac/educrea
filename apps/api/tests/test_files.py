from fastapi.testclient import TestClient

from test_auth_projects import register


def test_file_persistence_and_conflicts(client: TestClient):
    csrf = register(client, "teacher@example.org")
    headers = {"X-CSRF-Token": csrf}
    project = client.post("/api/projects", headers=headers, json={"title": "Fracciones"}).json()
    base = f"/api/projects/{project['id']}/files"
    created = client.post(base, headers=headers, json={"path": "activity.json", "content": '{"title":"Fracciones"}'})
    assert created.status_code == 201
    file = created.json()
    assert file["version"] == 1
    assert client.get(base).json()[0]["path"] == "activity.json"
    assert client.get(f"{base}/{file['id']}").json()["content"] == '{"title":"Fracciones"}'
    updated = client.put(f"{base}/{file['id']}", headers=headers,
                         json={"content": '{"title":"Sumas"}', "expected_version": 1})
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert client.put(f"{base}/{file['id']}", headers=headers,
                      json={"content": "stale", "expected_version": 1}).status_code == 409
    assert client.delete(f"{base}/{file['id']}?expected_version=1", headers=headers).status_code == 409
    assert client.get(f"{base}/{file['id']}").json()["content"] == '{"title":"Sumas"}'
    assert client.delete(f"{base}/{file['id']}?expected_version=2", headers=headers).status_code == 204


def test_paths_size_csrf_and_ownership(client: TestClient):
    first_csrf = register(client, "first@example.org")
    first_headers = {"X-CSRF-Token": first_csrf}
    project = client.post("/api/projects", headers=first_headers, json={"title": "Solar"}).json()
    base = f"/api/projects/{project['id']}/files"
    for path in ("../secret.js", "a/../../secret.js", "/absolute.html", "a\\b.js", "file.py", ".hidden.js"):
        assert client.post(base, headers=first_headers, json={"path": path}).status_code == 422
    assert client.post(base, headers=first_headers, json={"path": "index.html", "content": "é" * 140000}).status_code == 413
    assert client.post(base, json={"path": "index.html"}).status_code == 403
    file = client.post(base, headers=first_headers, json={"path": "index.html"}).json()
    assert client.post(base, headers=first_headers, json={"path": "index.html"}).status_code == 409
    client.post("/api/auth/logout", headers=first_headers)
    second_csrf = register(client, "second@example.org")
    second_headers = {"X-CSRF-Token": second_csrf}
    assert client.get(base).status_code == 404
    assert client.get(f"{base}/{file['id']}").status_code == 404
    assert client.put(f"{base}/{file['id']}", headers=second_headers,
                      json={"content": "stolen", "expected_version": 1}).status_code == 404
    assert client.delete(f"{base}/{file['id']}?expected_version=1", headers=second_headers).status_code == 404

