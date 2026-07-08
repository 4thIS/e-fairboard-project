import time
from datetime import datetime, timedelta, timezone

VALID_POST = {"title": "예약", "template_id": 0, "fields": {"0": "T"},
              "qr_url": ""}


def make_post(client, auth_headers) -> int:
    return client.post("/api/posts", json=VALID_POST,
                       headers=auth_headers).json()["id"]


def in_seconds(s: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=s)).isoformat()


def test_create_and_list_schedule(client, auth_headers):
    pid = make_post(client, auth_headers)
    res = client.post("/api/schedules",
                      json={"post_id": pid, "node_ids": [1],
                            "run_at": in_seconds(3600)},
                      headers=auth_headers)
    assert res.status_code == 201
    listed = client.get("/api/schedules", headers=auth_headers).json()
    assert listed[0]["status"] == "pending"


def test_schedule_fires_and_deploys(client, auth_headers):
    pid = make_post(client, auth_headers)
    client.post("/api/schedules",
                json={"post_id": pid, "node_ids": "all",
                      "run_at": in_seconds(0.2)},
                headers=auth_headers)
    deadline = time.monotonic() + 5.0
    deps = []
    while time.monotonic() < deadline:
        deps = client.get("/api/deployments", headers=auth_headers).json()
        if deps and deps[0]["status"] == "success":
            break
        time.sleep(0.05)
    else:
        raise AssertionError("scheduled deployment did not run")
    assert deps[0]["trigger"] == "scheduled"
    sched = client.get("/api/schedules", headers=auth_headers).json()[0]
    assert sched["status"] == "done"


def test_cancel_schedule(client, auth_headers):
    pid = make_post(client, auth_headers)
    sid = client.post("/api/schedules",
                      json={"post_id": pid, "node_ids": [1],
                            "run_at": in_seconds(3600)},
                      headers=auth_headers).json()["id"]
    assert client.delete(f"/api/schedules/{sid}",
                         headers=auth_headers).status_code == 204
    sched = client.get("/api/schedules", headers=auth_headers).json()[0]
    assert sched["status"] == "cancelled"


def test_schedule_unknown_post_404(client, auth_headers):
    res = client.post("/api/schedules",
                      json={"post_id": 999, "node_ids": [1],
                            "run_at": in_seconds(60)},
                      headers=auth_headers)
    assert res.status_code == 404


def test_pending_schedule_restored_after_restart(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import TEST_PASSWORD, make_settings

    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as c1:
        token = c1.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        pid = c1.post("/api/posts", json=VALID_POST, headers=h).json()["id"]
        c1.post("/api/schedules",
                json={"post_id": pid, "node_ids": [1],
                      "run_at": in_seconds(0.2)}, headers=h)
    # 재시작 — pending 예약이 부팅 시 재등록되어 실행된다
    with TestClient(create_app(settings)) as c2:
        token = c2.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            deps = c2.get("/api/deployments", headers=h).json()
            if deps and deps[0]["status"] != "running":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("restored schedule did not fire")
