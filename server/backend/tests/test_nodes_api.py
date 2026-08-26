def test_nodes_seeded_in_virtual_mode(client, auth_headers):
    nodes = client.get("/api/nodes", headers=auth_headers).json()
    assert {n["id"] for n in nodes} == {1, 2}
    assert all("history" not in n for n in nodes)


def test_node_detail_includes_display_state(client, auth_headers):
    res = client.get("/api/nodes/1", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["display_state"]["template_id"] is None  # 아직 배포 없음


def test_node_detail_404(client, auth_headers):
    assert client.get("/api/nodes/99", headers=auth_headers).status_code == 404


def test_ping_marks_node_online(client, auth_headers):
    res = client.post("/api/nodes/1/ping", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["batt_mv"] > 3000
    node = client.get("/api/nodes/1", headers=auth_headers).json()
    assert node["status"] == "online"


def test_ping_powered_off_marks_offline(client, auth_headers):
    client.post("/api/sim/nodes/1/power", json={"powered": False},
                headers=auth_headers)
    res = client.post("/api/nodes/1/ping", headers=auth_headers)
    assert res.json()["ok"] is False
    node = client.get("/api/nodes/1", headers=auth_headers).json()
    assert node["status"] == "offline"


def test_sim_config_roundtrip(client, auth_headers):
    client.put("/api/sim/config", json={"loss_rate": 0.3}, headers=auth_headers)
    cfg = client.get("/api/sim/config", headers=auth_headers).json()
    assert cfg["loss_rate"] == 0.3


def test_history_endpoint_empty_initially(client, auth_headers):
    assert client.get("/api/nodes/1/history", headers=auth_headers).json() == []


def test_list_nodes_includes_display_state(client, auth_headers):
    nodes = client.get("/api/nodes", headers=auth_headers).json()
    assert all("display_state" in n for n in nodes)


def test_create_and_delete_node(client, auth_headers):
    before = {n["id"] for n in client.get("/api/nodes", headers=auth_headers).json()}
    nid = max(before) + 5
    res = client.post("/api/nodes", json={"id": nid, "name": "새 노드"}, headers=auth_headers)
    assert res.status_code == 201 and res.json()["id"] == nid
    assert nid in {n["id"] for n in client.get("/api/nodes", headers=auth_headers).json()}
    # 중복 거부
    assert client.post("/api/nodes", json={"id": nid}, headers=auth_headers).status_code == 409
    # 범위 밖 거부
    assert client.post("/api/nodes", json={"id": 999}, headers=auth_headers).status_code == 422
    # 삭제
    assert client.delete(f"/api/nodes/{nid}", headers=auth_headers).status_code == 204
    assert nid not in {n["id"] for n in client.get("/api/nodes", headers=auth_headers).json()}
    assert client.delete(f"/api/nodes/{nid}", headers=auth_headers).status_code == 404
