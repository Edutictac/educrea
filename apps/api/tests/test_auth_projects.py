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

