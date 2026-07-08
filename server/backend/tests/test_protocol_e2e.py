import pytest

from app.config import Settings
from app.protocol.link import LinkManager, LinkTimeoutError
from app.protocol.packet import MsgType, build_set_field, build_set_qr, parse_pong
from app.simulator.rig import SimRig


def fast_settings(**over) -> Settings:
    # link_retries=12: 양방향 손실 30% 스트레스 대비 (운영 기본은 3)
    return Settings(_env_file=None, sim_airtime_s=0.0, ack_timeout_s=0.05,
                    link_retries=12, sim_refresh_partial_s=0.0,
                    sim_refresh_full_s=0.0, **over)


@pytest.fixture
async def rig():
    r = SimRig.build(fast_settings())
    await r.start()
    yield r
    await r.stop()


async def deploy_sequence(link: LinkManager, node_id: int):
    await link.request(node_id, MsgType.SET_TEMPLATE, b"\x00", expect=MsgType.ACK)
    await link.request(node_id, MsgType.SET_FIELD,
                       build_set_field(0, "임베디드 경진대회"), expect=MsgType.ACK)
    await link.request(node_id, MsgType.SET_QR,
                       build_set_qr("https://4this.io/e"), expect=MsgType.ACK)
    await link.request(node_id, MsgType.COMMIT, b"\x00", expect=MsgType.ACK)


async def test_full_deploy_updates_node_display(rig):
    await deploy_sequence(rig.link, 0x01)
    state = rig.nodes[0x01].display_state
    assert state["template_id"] == 0
    assert state["fields"]["0"] == "임베디드 경진대회"
    assert state["qr_url"] == "https://4this.io/e"


async def test_deploy_succeeds_with_30pct_loss(rig):
    rig.channel.loss_rate = 0.3  # 스펙 §8: 손실 30%에서도 재전송으로 성공
    for _ in range(3):  # 여러 번 반복해도 안정적으로 성공해야 함
        await deploy_sequence(rig.link, 0x02)
    assert rig.nodes[0x02].display_state["template_id"] == 0


async def test_powered_off_node_times_out(rig):
    rig.nodes[0x01].powered = False
    with pytest.raises(LinkTimeoutError):
        await rig.link.request(0x01, MsgType.PING, expect=MsgType.PONG)


async def test_ping_returns_battery(rig):
    pong = await rig.link.request(0x02, MsgType.PING, expect=MsgType.PONG)
    batt, _, _ = parse_pong(pong.payload)
    assert batt > 3000
