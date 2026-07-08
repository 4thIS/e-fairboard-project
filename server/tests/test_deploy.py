from app.bridge.gateway_link import GatewayLink
from app.core.deploy import deploy_post
from app.core.state import StateStore
from sim.fake_gateway import FakeGatewayTransport


async def make_env(tmp_path, **gw_kw):
    gw = FakeGatewayTransport(**gw_kw)
    link = GatewayLink(gw, timeout=0.3)
    await link.start()
    store = StateStore(tmp_path / "state.json")
    return gw, link, store


async def test_2노드_배포_성공(tmp_path):
    gw, link, store = await make_env(tmp_path)
    post = store.new_post(0, {0: "AI 경진대회", 1: "7/20 14:00"},
                          "https://ex.am/detail", [1, 2])
    result = await deploy_post(link, store, post)
    assert result.status == "deployed"
    assert result.ok_nodes == [1, 2] and not result.failed_nodes
    for nid in (1, 2):
        assert gw.nodes[nid].committed == {0: "AI 경진대회", 1: "7/20 14:00"}
        assert gw.nodes[nid].qr == {0: "https://ex.am/detail"}
        assert gw.nodes[nid].template_id == 0
        assert store.nodes[nid].online and store.nodes[nid].template_id == 0
    assert post.status == "deployed" and post.deployed_at
    assert store.stats.deploy_success == 2 and store.stats.paper_saved == 2
    await link.stop()


async def test_무응답_노드는_partial_및_offline(tmp_path):
    gw, link, store = await make_env(tmp_path)
    gw.nodes[0x02].silent = True
    post = store.new_post(0, {0: "제목"}, None, [1, 2])
    result = await deploy_post(link, store, post)
    assert result.status == "partial"
    assert result.ok_nodes == [1] and result.failed_nodes == [2]
    assert store.nodes[2].online is False and store.nodes[2].err_cnt == 1
    assert store.stats.deploy_fail == 1
    await link.stop()


async def test_전_노드_실패면_failed(tmp_path):
    gw, link, store = await make_env(tmp_path)
    gw.nodes[0x01].silent = True
    gw.nodes[0x02].silent = True
    post = store.new_post(0, {0: "제목"}, None, [1, 2])
    result = await deploy_post(link, store, post)
    assert result.status == "failed" and post.status == "failed"
    await link.stop()


async def test_같은_템플릿_재배포는_SET_TEMPLATE_생략_부분갱신(tmp_path):
    gw, link, store = await make_env(tmp_path)
    p1 = store.new_post(0, {0: "v1"}, None, [1])
    await deploy_post(link, store, p1)
    assert gw.nodes[1].last_refresh == 1        # 첫 배포: 템플릿 전환 → 전체갱신
    p2 = store.new_post(0, {0: "v2"}, None, [1])
    await deploy_post(link, store, p2)
    assert gw.nodes[1].last_refresh == 0        # 같은 템플릿: 부분갱신
    assert gw.nodes[1].committed == {0: "v2"}
    await link.stop()


async def test_node_ids_인자가_타깃_오버라이드(tmp_path):
    gw, link, store = await make_env(tmp_path)
    post = store.new_post(0, {0: "x"}, None, [1, 2])
    result = await deploy_post(link, store, post, node_ids=[1])
    assert result.ok_nodes == [1]
    assert gw.nodes[2].committed == {}
    await link.stop()
