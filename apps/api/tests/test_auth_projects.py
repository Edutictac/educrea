from fastapi.testclient import TestClient


def register(client: TestClient, email: str) -> str:
    response = client.post("/api/auth/register", json={"email": email, "password": "a-long-test-password"})
    assert response.status_code == 201
    return response.json()["csrf_token"]


def test_auth_session_and_csrf(client: TestClient):
    csrf = register(client, "teacher@example.org")
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    refreshed = response.json()["csrf_token"]
    assert client.post("/api/projects", json={"title": "Fracciones"}).status_code == 403
    assert client.post("/api/projects", headers={"X-CSRF-Token": csrf}, json={"title": "Antiguo"}).status_code == 403
    assert client.post("/api/projects", headers={"X-CSRF-Token": refreshed}, json={"title": "Fracciones"}).status_code == 201
    rotated = client.get("/api/auth/me").json()["csrf_token"]
    assert client.post("/api/projects", headers={"X-CSRF-Token": refreshed}, json={"title": "Antiguo"}).status_code == 403
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": rotated}).status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_credentials_and_project_isolation(client: TestClient):
    first_csrf = register(client, "first@example.org")
    response = client.post("/api/projects", headers={"X-CSRF-Token": first_csrf}, json={"title": "Solar"})
    project_id = response.json()["id"]
    client.post("/api/auth/logout", headers={"X-CSRF-Token": first_csrf})
    second_csrf = register(client, "second@example.org")
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert client.patch(f"/api/projects/{project_id}", headers={"X-CSRF-Token": second_csrf}, json={"title": "Robado"}).status_code == 404
    assert client.delete(f"/api/projects/{project_id}", headers={"X-CSRF-Token": second_csrf}).status_code == 404
    assert client.get("/api/projects").json() == []
    assert client.post("/api/auth/login", json={"email": "first@example.org", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "first@example.org", "password": "a-long-test-password"}).status_code == 200
    assert client.get(f"/api/projects/{project_id}").status_code == 200


def test_project_update_and_delete(client: TestClient):
    csrf = register(client, "teacher@example.org")
    headers = {"X-CSRF-Token": csrf}
    project = client.post("/api/projects", headers=headers, json={"title": "Lectura"}).json()
    project_id = project["id"]
    response = client.patch(f"/api/projects/{project_id}", headers=headers, json={"description": "Actividad"})
    assert response.status_code == 200
    assert response.json()["description"] == "Actividad"
    assert client.delete(f"/api/projects/{project_id}", headers=headers).status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404



def test_duplicate_project_copies_files_images_and_material_but_not_history(client):
    from pathlib import Path

    csrf = register(client, "dup@example.org")
    headers = {"X-CSRF-Token": csrf}
    project = client.post("/api/projects", headers=headers, json={"title": "Volcanes", "description": "3.º"}).json()
    base = f"/api/projects/{project['id']}"
    file = client.post(f"{base}/files", headers=headers, json={"path": "index.html", "content": "<h1>v1</h1>"}).json()
    client.put(f"{base}/files/{file['id']}", headers=headers, json={"content": "<h1>v2</h1>", "expected_version": 1})
    png = (Path(__file__).parent / "fixtures" / "trompeta.png").read_bytes()
    client.post(f"{base}/assets", headers={**headers, "Content-Type": "application/octet-stream"},
                params={"filename": "t.png", "alt": "Trompeta"}, content=png)
    client.post(f"{base}/sources", headers={**headers, "Content-Type": "application/octet-stream"},
                params={"filename": "apuntes.md", "title": "Apuntes"}, content="# Volcanes\n\nEl magma sale por el cráter.".encode())
    copy = client.post(f"{base}/duplicate", headers=headers)
    assert copy.status_code == 201, copy.text
    copy = copy.json()
    assert copy["id"] != project["id"] and copy["title"] == "Volcanes (copia)" and copy["description"] == "3.º"
    new = f"/api/projects/{copy['id']}"
    files = client.get(f"{new}/files").json()
    assert [(f["path"], f["version"]) for f in files] == [("index.html", 1)]
    assert client.get(f"{new}/files/{files[0]['id']}").json()["content"] == "<h1>v2</h1>"
    assert [a["alt"] for a in client.get(f"{new}/assets").json()] == ["Trompeta"]
    sources = client.get(f"{new}/sources").json()
    assert sources[0]["title"] == "Apuntes"
    assert client.get(f"{new}/sources/{sources[0]['id']}/search", params={"q": "magma cráter"}).json()
    assert client.get(f"{new}/history", params={"path": "index.html"}).json()[0]["version"] == 1
    client.post("/api/auth/logout", headers=headers)
    other = {"X-CSRF-Token": register(client, "otro-dup@example.org")}
    assert client.post(f"{base}/duplicate", headers=other).status_code == 404
