VALID = {"title": "행사 안내", "template_id": 0,
         "fields": {"0": "임베디드 대회", "1": "7/20 10:00"},
         "qr_url": "https://4this.io"}


def test_requires_auth(client):
    assert client.get("/api/posts").status_code == 401


def test_templates_endpoint(client, auth_headers):
    res = client.get("/api/templates", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()) == 4


def test_create_and_get_post(client, auth_headers):
    res = client.post("/api/posts", json=VALID, headers=auth_headers)
    assert res.status_code == 201
    pid = res.json()["id"]
    got = client.get(f"/api/posts/{pid}", headers=auth_headers).json()
    assert got["title"] == "행사 안내"
    assert got["fields"]["0"] == "임베디드 대회"


def test_create_rejects_unknown_template(client, auth_headers):
    bad = dict(VALID, template_id=9)
    assert client.post("/api/posts", json=bad,
                       headers=auth_headers).status_code == 422


def test_create_rejects_field_over_max_bytes(client, auth_headers):
    bad = dict(VALID, fields={"0": "가" * 30})  # 90B > 제목 60B
    assert client.post("/api/posts", json=bad,
                       headers=auth_headers).status_code == 422


def test_create_rejects_unknown_field_id(client, auth_headers):
    bad = dict(VALID, fields={"7": "x"})
    assert client.post("/api/posts", json=bad,
                       headers=auth_headers).status_code == 422


def test_update_post(client, auth_headers):
    pid = client.post("/api/posts", json=VALID, headers=auth_headers).json()["id"]
    res = client.put(f"/api/posts/{pid}", json=dict(VALID, title="수정됨"),
                     headers=auth_headers)
    assert res.status_code == 200 and res.json()["title"] == "수정됨"


def test_delete_post(client, auth_headers):
    pid = client.post("/api/posts", json=VALID, headers=auth_headers).json()["id"]
    assert client.delete(f"/api/posts/{pid}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/posts/{pid}", headers=auth_headers).status_code == 404


def test_posts_persist_across_restart(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import TEST_PASSWORD, make_settings

    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as c1:
        token = c1.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
        c1.post("/api/posts", json=VALID,
                headers={"Authorization": f"Bearer {token}"})
    with TestClient(create_app(settings)) as c2:
        token = c2.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
        posts = c2.get("/api/posts",
                       headers={"Authorization": f"Bearer {token}"}).json()
        assert len(posts) == 1  # JSON 스냅샷에서 복원됨
