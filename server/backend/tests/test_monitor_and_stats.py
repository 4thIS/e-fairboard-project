import pytest

from app.config import Settings
from app.services.node_service import NodeMonitor
from app.services.stats_service import summary
from app.simulator.rig import SimRig
from app.store import Store


def fast_settings(tmp_path) -> Settings:
    return Settings(_env_file=None, sim_airtime_s=0.0, ack_timeout_s=0.05,
                    sim_refresh_partial_s=0.0, sim_refresh_full_s=0.0,
                    data_file=str(tmp_path / "state.json"))


@pytest.fixture
async def rig_and_store(tmp_path):
    settings = fast_settings(tmp_path)
    rig = SimRig.build(settings)
    await rig.start()
    store = Store(tmp_path / "state.json")
    store.load()
    store.seed_nodes([0x01, 0x02])
    yield rig, store
    await rig.stop()


async def test_poll_once_marks_online_and_appends_history(rig_and_store):
    rig, store = rig_and_store
    monitor = NodeMonitor(store, rig, interval_s=3600)
    await monitor.poll_once()
    node = store.state.nodes[0x01]
    assert node.status == "online"
    assert node.batt_mv and node.batt_mv > 3000
    assert len(node.history) == 1


async def test_two_consecutive_misses_mark_offline(rig_and_store):
    rig, store = rig_and_store
    monitor = NodeMonitor(store, rig, interval_s=3600)
    rig.nodes[0x02].powered = False
    await monitor.poll_once()
    assert store.state.nodes[0x02].status != "offline"  # 1회 실패는 유예
    await monitor.poll_once()
    assert store.state.nodes[0x02].status == "offline"


async def test_success_resets_miss_count(rig_and_store):
    rig, store = rig_and_store
    monitor = NodeMonitor(store, rig, interval_s=3600)
    rig.nodes[0x01].powered = False
    await monitor.poll_once()
    rig.nodes[0x01].powered = True
    await monitor.poll_once()
    rig.nodes[0x01].powered = False
    await monitor.poll_once()
    assert store.state.nodes[0x01].status == "online"  # 아직 1회 실패


def test_stats_summary_counts(client, auth_headers):
    post = {"title": "T", "template_id": 0, "fields": {"0": "A"}, "qr_url": ""}
    pid = client.post("/api/posts", json=post, headers=auth_headers).json()["id"]
    import time
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": "all", "refresh_mode": 0},
                      headers=auth_headers)
    dep_id = res.json()["id"]
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if client.get(f"/api/deployments/{dep_id}",
                      headers=auth_headers).json()["status"] != "running":
            break
        time.sleep(0.02)
    stats = client.get("/api/stats/summary", headers=auth_headers).json()
    assert stats["deployments_total"] == 1
    assert stats["targets_success"] == 2
    assert stats["paper_saved"] == 2
    assert stats["success_rate"] == 1.0
