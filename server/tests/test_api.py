from fastapi.testclient import TestClient

from app import config


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(config, "SERIAL_PORT", None)      # FakeGW 모드
    monkeypatch.setattr(config, "DATA_PATH", tmp_path / "state.json")
    monkeypatch.setattr(config, "LINK_TIMEOUT", 0.3)
    from app.main import app
    return TestClient(app)


def test_health_및_templates(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        assert c.get("/api/health").json()["ok"] is True
        tpls = c.get("/api/templates").json()
        assert len(tpls) == 4
        assert tpls[0]["name"] == "행사 안내"


def test_post_CRUD(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        r = c.post("/api/posts", json={
            "template_id": 0,
            "fields": {"0": "AI 경진대회", "1": "7/20 14:00"},
            "qr_url": "https://ex.am/1",
            "target_node_ids": [1, 2]})
        assert r.status_code == 201
        pid = r.json()["id"]
        assert c.get(f"/api/posts/{pid}").json()["fields"]["0"] == "AI 경진대회"
        r = c.put(f"/api/posts/{pid}", json={
            "template_id": 0, "fields": {"0": "수정됨"},
            "qr_url": None, "target_node_ids": [1]})
        assert r.json()["fields"]["0"] == "수정됨"
        assert c.delete(f"/api/posts/{pid}").status_code == 204
        assert c.get(f"/api/posts/{pid}").status_code == 404


def test_잘못된_필드는_422(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        r = c.post("/api/posts", json={
            "template_id": 0, "fields": {"9": "없는 필드"},
            "qr_url": None, "target_node_ids": []})
        assert r.status_code == 422


def test_배포_E2E_노드_online_및_통계(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        pid = c.post("/api/posts", json={
            "template_id": 0, "fields": {"0": "공지"},
            "qr_url": "https://ex.am/q", "target_node_ids": [1, 2]}).json()["id"]
        r = c.post(f"/api/posts/{pid}/deploy", json={})
        assert r.json() == {"status": "deployed", "ok_nodes": [1, 2], "failed_nodes": []}
        nodes = {n["node_id"]: n for n in c.get("/api/nodes").json()}
        assert nodes[1]["online"] and nodes[2]["online"]
        stats = c.get("/api/stats").json()
        assert stats["paper_saved"] == 2


def test_ping과_status(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        r = c.post("/api/nodes/1/ping")
        assert r.status_code == 200
        assert r.json()["batt_mv"] == 3900
        r = c.post("/api/nodes/1/status")
        assert r.json()["batt_mv"] == 3900
        r = c.post("/api/nodes/99/ping")
        assert r.status_code == 404


def test_예약_등록과_취소(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        pid = c.post("/api/posts", json={
            "template_id": 0, "fields": {"0": "예약"},
            "qr_url": None, "target_node_ids": [1]}).json()["id"]
        r = c.post(f"/api/posts/{pid}/schedule",
                   json={"at": "2099-01-01T00:00:00+00:00"})
        assert r.status_code == 200
        assert c.get(f"/api/posts/{pid}").json()["status"] == "scheduled"
        assert c.delete(f"/api/posts/{pid}/schedule").status_code == 200
        assert c.get(f"/api/posts/{pid}").json()["status"] == "draft"
