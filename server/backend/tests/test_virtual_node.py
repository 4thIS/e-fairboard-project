import asyncio

import pytest

from app.protocol.packet import (
    GATEWAY_ID, AckResult, MsgType, Packet,
    build_set_field, build_set_qr, parse_ack, parse_pong, parse_status_res,
)
from app.simulator.channel import VirtualChannel
from app.simulator.node import VirtualNode


class GatewaySpy:
    """채널에 참여해 노드 응답을 수집하는 게이트웨이 대역."""

    node_id = GATEWAY_ID

    def __init__(self):
        self.inbox: asyncio.Queue[Packet] = asyncio.Queue()

    async def on_air(self, pkt: Packet):
        await self.inbox.put(pkt)

    async def send_and_wait(self, channel, pkt: Packet) -> Packet:
        await channel.transmit(pkt)
        return await asyncio.wait_for(self.inbox.get(), timeout=1.0)


@pytest.fixture
def rig():
    channel = VirtualChannel(airtime_s=0.0, loss_rate=0.0)
    node = VirtualNode(0x01, channel, refresh_partial_s=0.0, refresh_full_s=0.0)
    gw = GatewaySpy()
    channel.attach(node)
    channel.attach(gw)
    return channel, node, gw


async def test_set_field_stages_but_does_not_display(rig):
    channel, node, gw = rig
    ack = await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.SET_FIELD, 1, build_set_field(0, "제목")))
    assert parse_ack(ack.payload) == (1, AckResult.OK)
    assert node.display_state["fields"] == {}  # 커밋 전이므로 화면 없음


async def test_commit_applies_staged_state(rig):
    channel, node, gw = rig
    await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.SET_TEMPLATE, 1, b"\x02"))
    await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.SET_FIELD, 2, build_set_field(0, "모집")))
    await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.SET_QR, 3, build_set_qr("https://x.io")))
    await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.COMMIT, 4, b"\x00"))
    state = node.display_state
    assert state["template_id"] == 2
    assert state["fields"] == {"0": "모집"}
    assert state["qr_url"] == "https://x.io"
    assert state["last_commit_at"] is not None


async def test_duplicate_seq_is_idempotent(rig):
    channel, node, gw = rig
    pkt = Packet(GATEWAY_ID, 0x01, MsgType.SET_FIELD, 9, build_set_field(0, "A"))
    ack1 = await gw.send_and_wait(channel, pkt)
    ack2 = await gw.send_and_wait(channel, pkt)  # 동일 (TYPE,SEQ) 재전송
    assert parse_ack(ack1.payload) == parse_ack(ack2.payload) == (9, AckResult.OK)
    # 스테이징이 한 번만 적용됐는지는 커밋 후 값으로 확인
    await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.COMMIT, 10, b"\x00"))
    assert node.display_state["fields"]["0"] == "A"


async def test_ping_pong_reports_battery(rig):
    channel, node, gw = rig
    pong = await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.PING, 5))
    assert pong.type == MsgType.PONG
    batt, rssi, status = parse_pong(pong.payload)
    assert 3000 < batt <= 4200 and rssi < 0


async def test_status_res_fields(rig):
    channel, node, gw = rig
    await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.SET_TEMPLATE, 1, b"\x00"))
    res = await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.STATUS_REQ, 2))
    batt, last_seq, uptime, err = parse_status_res(res.payload)
    assert res.type == MsgType.STATUS_RES and last_seq == 1 and err == 0


async def test_powered_off_node_is_silent(rig):
    channel, node, gw = rig
    node.powered = False
    await channel.transmit(Packet(GATEWAY_ID, 0x01, MsgType.PING, 6))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(gw.inbox.get(), timeout=0.05)


async def test_unsupported_type_acks_bad_type(rig):
    channel, node, gw = rig
    ack = await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.IMG_FRAG, 7, b"\x00"))
    assert parse_ack(ack.payload) == (7, AckResult.BAD_TYPE)


async def test_channel_loss_drops_packet():
    channel = VirtualChannel(airtime_s=0.0, loss_rate=1.0)
    node = VirtualNode(0x01, channel, refresh_partial_s=0.0, refresh_full_s=0.0)
    gw = GatewaySpy()
    channel.attach(node)
    channel.attach(gw)
    await channel.transmit(Packet(GATEWAY_ID, 0x01, MsgType.PING, 1))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(gw.inbox.get(), timeout=0.05)


async def test_broadcast_reaches_all_nodes():
    channel = VirtualChannel(airtime_s=0.0, loss_rate=0.0)
    n1 = VirtualNode(0x01, channel, refresh_partial_s=0.0, refresh_full_s=0.0)
    n2 = VirtualNode(0x02, channel, refresh_partial_s=0.0, refresh_full_s=0.0)
    gw = GatewaySpy()
    for p in (n1, n2, gw):
        channel.attach(p)
    await channel.transmit(Packet(GATEWAY_ID, 0xFF, MsgType.SET_TEMPLATE, 1, b"\x01"))
    acks = [await asyncio.wait_for(gw.inbox.get(), timeout=1.0) for _ in range(2)]
    assert {a.src for a in acks} == {0x01, 0x02}


async def test_fragmented_field_reassembles(rig):
    from app.protocol.packet import build_set_field_fragments
    channel, node, gw = rig
    long_text = "가" * 150  # 450B > 198 → 여러 조각
    frags = build_set_field_fragments(0, long_text)
    assert len(frags) >= 2  # 실제로 쪼개졌는지
    await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.SET_TEMPLATE, 1, b"\x02"))
    seq = 10
    for payload, frag in frags:
        await gw.send_and_wait(channel, Packet(
            GATEWAY_ID, 0x01, MsgType.SET_FIELD, seq, payload, frag=frag))
        seq += 1
    await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.COMMIT, seq, b"\x00"))
    assert node.display_state["fields"]["0"] == long_text


async def test_fragment_retransmit_no_double_append(rig):
    from app.protocol.packet import build_set_field_fragments
    channel, node, gw = rig
    frags = build_set_field_fragments(0, "나" * 100)  # 여러 조각
    assert len(frags) >= 2
    await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.SET_TEMPLATE, 1, b"\x02"))
    seq = 10
    for i, (payload, frag) in enumerate(frags):
        pkt = Packet(GATEWAY_ID, 0x01, MsgType.SET_FIELD, seq, payload, frag=frag)
        await gw.send_and_wait(channel, pkt)
        if i == 0:
            await gw.send_and_wait(channel, pkt)  # 조각0 재전송 — dedup, 이중 append 없어야
        seq += 1
    await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.COMMIT, seq, b"\x00"))
    assert node.display_state["fields"]["0"] == "나" * 100  # 이중 append 면 길이가 늘어 실패
