import time

VALID_POST = {"title": "폐막식 안내", "template_id": 0,
              "fields": {"0": "폐막식", "1": "7/21 17:00", "2": "대강당"},
              "qr_url": "https://4this.io/closing"}


def wait_done(client, headers, dep_id, timeout=10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dep = client.get(f"/api/deployments/{dep_id}", headers=headers).json()
        if dep["status"] != "running":
            return dep
        time.sleep(0.02)
    raise AssertionError("deployment stuck")


def test_demo_scenario_end_to_end(client, auth_headers):
    """데모 시나리오: 손실 30% 설정 → 게시물 작성 → 일괄 배포 → 성공 →
    노드 화면 확인 → 통계 반영 → 노드 전원 차단 → 재배포 → partial."""
    h = auth_headers
    # 1) 악조건 설정 (재전송 경로 검증)
    client.put("/api/sim/config", json={"loss_rate": 0.3}, headers=h)
    # 2) 게시물 작성
    pid = client.post("/api/posts", json=VALID_POST, headers=h).json()["id"]
    # 3) 일괄 배포 → 성공
    dep_id = client.post("/api/deployments",
                         json={"post_id": pid, "node_ids": "all",
                               "refresh_mode": 1},
                         headers=h).json()["id"]
    assert wait_done(client, h, dep_id)["status"] == "success"
    # 4) 두 노드 화면 상태 일치
    for nid in (1, 2):
        state = client.get(f"/api/nodes/{nid}", headers=h).json()["display_state"]
        assert state["fields"]["0"] == "폐막식"
        assert state["qr_url"] == "https://4this.io/closing"
    # 5) 통계 반영
    stats = client.get("/api/stats/summary", headers=h).json()
    assert stats["paper_saved"] == 2 and stats["success_rate"] == 1.0
    # 6) 노드2 전원 차단 → 재배포 → partial
    client.post("/api/sim/nodes/2/power", json={"powered": False}, headers=h)
    dep2 = client.post("/api/deployments",
                       json={"post_id": pid, "node_ids": "all",
                             "refresh_mode": 0},
                       headers=h).json()["id"]
    result = wait_done(client, h, dep2)
    assert result["status"] == "partial"
    assert client.get("/api/nodes/2", headers=h).json()["status"] == "offline"
