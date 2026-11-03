from fastapi.testclient import TestClient

from test_auth_projects import register


def make(client: TestClient, email="h@example.org"):
    headers = {"X-CSRF-Token": register(client, email)}
    project = client.post("/api/projects", headers=headers, json={"title": "Notas"}).json()
    base = f"/api/projects/{project['id']}"
    file = client.post(f"{base}/files", headers=headers, json={"path": "index.html", "content": "v1"}).json()
    return headers, base, file


def save(client, headers, base, file, content):
    return client.put(f"{base}/files/{file['id']}", headers=headers,
                      json={"content": content, "expected_version": file["version"]}).json()


def test_each_save_creates_a_version_and_restore_appends(client: TestClient):
    headers, base, file = make(client)
    file = save(client, headers, base, file, "v2")
    file = save(client, headers, base, file, "v3")
    versions = client.get(f"{base}/history", params={"path": "index.html"}).json()
    assert [v["version"] for v in versions] == [3, 2, 1]
    first = versions[-1]
    assert client.get(f"{base}/history/{first['id']}").json()["content"] == "v1"
    restored = client.post(f"{base}/history/{first['id']}/restore", headers=headers)
    assert restored.status_code == 200 and restored.json()["version"] == 4 and restored.json()["source"] == "restore"
    current = client.get(f"{base}/files").json()[0]
    assert current["version"] == 4
    assert client.get(f"{base}/files/{current['id']}").json()["content"] == "v1"
    assert len(client.get(f"{base}/history", params={"path": "index.html"}).json()) == 4


def test_deleted_file_can_be_recovered(client: TestClient):
    headers, base, file = make(client)
    file = save(client, headers, base, file, "v2")
    assert client.delete(f"{base}/files/{file['id']}?expected_version=2", headers=headers).status_code == 204
    paths = client.get(f"{base}/history/paths").json()
    assert paths == [{"path": "index.html", "versions": 2, "deleted": True}]
    last = client.get(f"{base}/history", params={"path": "index.html"}).json()[0]
    assert client.post(f"{base}/history/{last['id']}/restore", headers=headers).status_code == 200
    recovered = client.get(f"{base}/files").json()[0]
    assert recovered["path"] == "index.html" and recovered["version"] == 3
    assert client.get(f"{base}/files/{recovered['id']}").json()["content"] == "v2"


def test_history_is_private_and_needs_csrf(client: TestClient):
    headers, base, file = make(client)
    version = client.get(f"{base}/history", params={"path": "index.html"}).json()[0]
    assert client.post(f"{base}/history/{version['id']}/restore").status_code == 403
    client.post("/api/auth/logout", headers=headers)
    other = {"X-CSRF-Token": register(client, "other@example.org")}
    assert client.get(f"{base}/history", params={"path": "index.html"}).status_code == 404
    assert client.get(f"{base}/history/{version['id']}").status_code == 404
    assert client.post(f"{base}/history/{version['id']}/restore", headers=other).status_code == 404


def test_history_is_capped_per_path(client: TestClient):
    headers, base, file = make(client)
    for index in range(60):
        file = save(client, headers, base, file, f"c{index}")
    versions = client.get(f"{base}/history", params={"path": "index.html"}).json()
    assert len(versions) == 50 and versions[0]["version"] == 61
