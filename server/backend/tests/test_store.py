from datetime import datetime, timezone

from app.models import AppState, NodeInfo, Post, StatusSample
from app.store import HISTORY_MAX, Store


def now():
    return datetime.now(timezone.utc)


def test_load_missing_file_gives_empty_state(tmp_path):
    store = Store(tmp_path / "state.json")
    store.load()
    assert store.state == AppState()


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "data" / "state.json"  # 하위 디렉토리 자동 생성 확인
    store = Store(path)
    store.load()
    pid = store.next_id("post")
    store.state.posts[pid] = Post(id=pid, title="행사", template_id=0,
                                  fields={"0": "제목"}, created_at=now(),
                                  updated_at=now())
    store.save()

    fresh = Store(path)
    fresh.load()
    assert fresh.state.posts[pid].title == "행사"
    assert fresh.state.next_post_id == 2


def test_corrupt_file_is_backed_up_and_reset(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ not json !", encoding="utf-8")
    store = Store(path)
    store.load()
    assert store.state == AppState()
    assert path.with_suffix(".json.bak").exists()


def test_next_id_increments_per_counter(tmp_path):
    store = Store(tmp_path / "s.json")
    store.load()
    assert store.next_id("post") == 1
    assert store.next_id("post") == 2
    assert store.next_id("deployment") == 1


def test_history_ring_buffer_capped(tmp_path):
    store = Store(tmp_path / "s.json")
    store.load()
    store.seed_nodes([1])
    for i in range(HISTORY_MAX + 10):
        store.add_history(1, StatusSample(t=now(), batt_mv=4000 - i, rssi=-60))
    hist = store.state.nodes[1].history
    assert len(hist) == HISTORY_MAX
    assert hist[-1].batt_mv == 4000 - (HISTORY_MAX + 9)  # 최신이 마지막


def test_seed_nodes_does_not_overwrite_existing(tmp_path):
    store = Store(tmp_path / "s.json")
    store.load()
    store.state.nodes[1] = NodeInfo(id=1, name="1층 로비")
    store.seed_nodes([1, 2])
    assert store.state.nodes[1].name == "1층 로비"
    assert store.state.nodes[2].name == "노드 2"
