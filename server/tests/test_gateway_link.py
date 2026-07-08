import asyncio

import pytest

from app.bridge.gateway_link import GatewayLink, LinkTimeout
from app.protocol import cobs
from app.protocol.const import GATEWAY_ID, MsgType
from app.protocol.packet import Packet
from tests.conftest import MemoryTransport


def frame(pkt: Packet) -> bytes:
    return cobs.encode(pkt.encode()) + b"\x00"


def ack_for(pkt: Packet, result: int = 0) -> Packet:
    return Packet(src=pkt.dst, dst=GATEWAY_ID, type=MsgType.ACK, seq=pkt.seq,
                  payload=bytes([pkt.seq, result]))


async def make_link(**kw):
    t = MemoryTransport()
    link = GatewayLink(t, timeout=0.2, **kw)
    await link.start()
    return t, link


async def test_request가_매칭되는_ACK를_반환():
    t, link = await make_link()
    pkt = Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.SET_TEMPLATE,
                 seq=link.next_seq(0x01), payload=b"\x00")
    asyncio.get_running_loop().call_later(0.02, t.feed, frame(ack_for(pkt)))
    resp = await link.request(pkt, MsgType.ACK)
    assert resp.payload[0] == pkt.seq
    assert bytes(t.tx) == frame(pkt)   # 송신 프레임 = COBS+0x00
    await link.stop()


async def test_다른_seq의_늦은_ACK는_무시하고_타임아웃():
    t, link = await make_link()
    pkt = Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.COMMIT,
                 seq=link.next_seq(0x01), payload=b"\x00")
    stale = Packet(src=0x01, dst=GATEWAY_ID, type=MsgType.ACK, seq=99,
                   payload=bytes([99, 0]))
    asyncio.get_running_loop().call_later(0.02, t.feed, frame(stale))
    with pytest.raises(LinkTimeout):
        await link.request(pkt, MsgType.ACK)
    await link.stop()


async def test_쓰레기_프레임은_폐기하고_다음_프레임은_정상처리():
    t, link = await make_link()
    pkt = Packet(src=GATEWAY_ID, dst=0x02, type=MsgType.PING, seq=link.next_seq(0x02))
    pong = Packet(src=0x02, dst=GATEWAY_ID, type=MsgType.PONG, seq=pkt.seq,
                  payload=b"\x3c\x0f\xc4\x00")
    asyncio.get_running_loop().call_later(
        0.02, t.feed, b"\x07garbage\x00" + frame(pong))
    resp = await link.request(pkt, MsgType.PONG)
    assert resp.type == MsgType.PONG
    assert link.rx_dropped == 1
    await link.stop()


async def test_seq는_노드별로_증가하고_0xFF에서_롤오버():
    _, link = await make_link()
    assert link.next_seq(0x01) == 0
    assert link.next_seq(0x01) == 1
    assert link.next_seq(0x02) == 0        # 노드별 독립
    link._seq[0x03] = 0xFE
    assert link.next_seq(0x03) == 0xFF
    assert link.next_seq(0x03) == 0x00     # 롤오버
    await link.stop()


async def test_비요청_패킷은_on_event_콜백으로():
    events = []
    t, link = await make_link(on_event=events.append)
    pong = Packet(src=0x01, dst=GATEWAY_ID, type=MsgType.PONG, seq=7,
                  payload=b"\x3c\x0f\xc4\x00")
    t.feed(frame(pong))
    await asyncio.sleep(0.05)
    assert events and events[0].type == MsgType.PONG
    await link.stop()


async def test_한_read청크에_여러_프레임():
    events = []
    t, link = await make_link(on_event=events.append)
    p1 = Packet(src=0x01, dst=GATEWAY_ID, type=MsgType.PONG, seq=1, payload=b"\x00\x00\x00\x00")
    p2 = Packet(src=0x02, dst=GATEWAY_ID, type=MsgType.PONG, seq=2, payload=b"\x00\x00\x00\x00")
    t.feed(frame(p1) + frame(p2))
    await asyncio.sleep(0.05)
    assert [e.src for e in events] == [0x01, 0x02]
    await link.stop()
