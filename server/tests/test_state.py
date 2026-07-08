import json

from app.core.state import Node, Post, StateStore


def test_파일_없으면_기본_노드_2대(tmp_path):
    store = StateStore(tmp_path / "state.json")
    assert sorted(store.nodes) == [0x01, 0x02]
    assert store.nodes[0x01].name == "노드1"
    assert store.stats.deploy_success == 0


def test_저장_후_재로드_왕복(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    post = store.new_post(template_id=0, fields={0: "제목", 1: "7/20"},
                          qr_url="https://ex.am/1", target_node_ids=[1, 2])
    store.nodes[0x01].batt_mv = 3812
    store.stats.paper_saved = 5
    store.save()

    re = StateStore(path)
    assert re.posts[post.id].fields == {0: "제목", 1: "7/20"}   # int 키 보존
    assert re.posts[post.id].qr_url == "https://ex.am/1"
    assert re.nodes[0x01].batt_mv == 3812
    assert re.stats.paper_saved == 5


def test_new_post는_id를_발급하고_즉시_영속(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    post = store.new_post(0, {}, None, [])
    assert len(post.id) == 8
    assert post.status == "draft"
    assert post.id in json.loads(path.read_text())["posts"]


def test_원자적_쓰기_tmp파일_잔존_없음(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.save()
    assert path.exists()
    assert not path.with_suffix(".tmp").exists()
    json.loads(path.read_text())   # 항상 유효한 JSON
