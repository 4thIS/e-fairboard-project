import time

VALID_POST = {"title": "행사", "template_id": 0,
              "fields": {"0": "제목", "1": "일시"}, "qr_url": "https://x.io"}


def make_post(client, auth_headers) -> int:
    return client.post("/api/posts", json=VALID_POST,
                       headers=auth_headers).json()["id"]


def wait_deployment(client, auth_headers, dep_id, timeout=5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dep = client.get(f"/api/deployments/{dep_id}",
                         headers=auth_headers).json()
        if dep["status"] != "running":
            return dep
        time.sleep(0.02)
    raise AssertionError("deployment did not finish")


def test_deploy_to_all_nodes_success(client, auth_headers):
    pid = make_post(client, auth_headers)
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": "all", "refresh_mode": 0},
                      headers=auth_headers)
    assert res.status_code == 202
    dep = wait_deployment(client, auth_headers, res.json()["id"])
    assert dep["status"] == "success"
    assert {t["node_id"] for t in dep["targets"]} == {1, 2}
    assert all(t["status"] == "success" for t in dep["targets"])
    # 노드 화면·current_post_id 반영 확인
    node = client.get("/api/nodes/1", headers=auth_headers).json()
    assert node["current_post_id"] == pid
    assert node["display_state"]["fields"]["0"] == "제목"


def test_deploy_single_node(client, auth_headers):
    pid = make_post(client, auth_headers)
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": [2], "refresh_mode": 1},
                      headers=auth_headers)
    dep = wait_deployment(client, auth_headers, res.json()["id"])
    assert [t["node_id"] for t in dep["targets"]] == [2]
    node1 = client.get("/api/nodes/1", headers=auth_headers).json()
    assert node1["display_state"]["template_id"] is None  # 노드1은 미배포


def test_deploy_partial_when_one_node_off(client, auth_headers):
    client.post("/api/sim/nodes/2/power", json={"powered": False},
                headers=auth_headers)
    pid = make_post(client, auth_headers)
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": "all", "refresh_mode": 0},
                      headers=auth_headers)
    dep = wait_deployment(client, auth_headers, res.json()["id"])
    assert dep["status"] == "partial"
    by_node = {t["node_id"]: t for t in dep["targets"]}
    assert by_node[1]["status"] == "success"
    assert by_node[2]["status"] == "failed" and by_node[2]["error"]
    node2 = client.get("/api/nodes/2", headers=auth_headers).json()
    assert node2["status"] == "offline"


def test_deploy_unknown_post_404(client, auth_headers):
    res = client.post("/api/deployments",
                      json={"post_id": 999, "node_ids": "all", "refresh_mode": 0},
                      headers=auth_headers)
    assert res.status_code == 404


def test_running_deployment_marked_failed_on_boot(tmp_path):
    """서버가 배포 도중 죽었다 재시작하면 running → failed(interrupted) (스펙 §7)."""
    from datetime import datetime, timezone

    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.models import Deployment, DeployTarget
    from app.store import Store
    from tests.conftest import TEST_PASSWORD, make_settings

    settings = make_settings(tmp_path)
    store = Store(tmp_path / "state.json")
    store.load()
    store.state.deployments[1] = Deployment(
        id=1, post_id=1, status="running",
        created_at=datetime.now(timezone.utc),
        targets=[DeployTarget(node_id=1, status="sending")])
    store.state.next_deployment_id = 2
    store.save()

    with TestClient(create_app(settings)) as c:
        token = c.post("/api/auth/login",
                       json={"password": TEST_PASSWORD}).json()["token"]
        dep = c.get("/api/deployments/1",
                    headers={"Authorization": f"Bearer {token}"}).json()
    assert dep["status"] == "failed"
    assert dep["targets"][0]["status"] == "failed"
    assert dep["targets"][0]["error"] == "interrupted"


def test_deploy_reports_step_progress(client, auth_headers):
    pid = make_post(client, auth_headers)
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": [1], "refresh_mode": 0},
                      headers=auth_headers)
    dep = wait_deployment(client, auth_headers, res.json()["id"])
    t = dep["targets"][0]
    # VALID_POST = 필드 2 + QR → SET_TEMPLATE + SET_FIELD×2 + SET_QR + COMMIT = 5
    assert t["step_total"] == 5
    assert t["step_index"] == 5          # 마지막 단계까지 진행
    assert t["step_name"] == "COMMIT"


def test_deployment_list_ordering(client, auth_headers):
    pid = make_post(client, auth_headers)
    ids = []
    for _ in range(2):
        res = client.post("/api/deployments",
                          json={"post_id": pid, "node_ids": [1], "refresh_mode": 0},
                          headers=auth_headers)
        ids.append(res.json()["id"])
        wait_deployment(client, auth_headers, ids[-1])
    listed = client.get("/api/deployments", headers=auth_headers).json()
    assert [d["id"] for d in listed][:2] == sorted(ids, reverse=True)
