import asyncio
import struct

import pytest

from app.protocol import cobs
from app.protocol.const import BROADCAST_ID, GATEWAY_ID, AckResult, MsgType
from app.protocol.packet import Packet, decode
from sim.fake_gateway import FakeGatewayTransport, VirtualNode


def frame(pkt: Packet) -> bytes:
    return cobs.encode(pkt.encode()) + b"\x00"


async def roundtrip(gw: FakeGatewayTransport, pkt: Packet) -> Packet:
    await gw.write(frame(pkt))
    raw = await asyncio.wait_for(gw.read(), 1.0)
    return decode(cobs.decode(raw.rstrip(b"\x00")))


async def test_PING에_PONG_응답():
    gw = FakeGatewayTransport()
    resp = await roundtrip(gw, Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.PING, seq=0))
    assert resp.type == MsgType.PONG and resp.src == 0x01
    batt, rssi = struct.unpack("<Hb", resp.payload[:3])
    assert batt == 3900 and rssi == -60


async def test_SET_FIELD와_COMMIT_흐름():
    gw = FakeGatewayTransport()
    node = gw.nodes[0x01]
    text = "행사안내".encode()
    r1 = await roundtrip(gw, Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.SET_FIELD,
                                    seq=1, payload=bytes([0, len(text)]) + text))
    assert r1.type == MsgType.ACK and r1.payload[1] == AckResult.OK
    assert node.staging == {0: "행사안내"} and node.committed == {}
    r2 = await roundtrip(gw, Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.COMMIT,
                                    seq=2, payload=b"\x01"))
    assert r2.payload[1] == AckResult.OK
    assert node.committed == {0: "행사안내"} and node.last_refresh == 1


async def test_중복_SEQ는_재적용_없이_동일_ACK():
    gw = FakeGatewayTransport()
    node = gw.nodes[0x02]
    pkt = Packet(src=GATEWAY_ID, dst=0x02, type=MsgType.SET_TEMPLATE, seq=5, payload=b"\x02")
    r1 = await roundtrip(gw, pkt)
    node.template_id = 99            # 재적용되면 다시 2로 덮일 것
    r2 = await roundtrip(gw, pkt)    # 같은 (TYPE,SEQ)
    assert r1 == r2
    assert node.template_id == 99    # 멱등: 재적용 안 됨


async def test_silent_노드는_무응답():
    gw = FakeGatewayTransport()
    gw.nodes[0x01].silent = True
    await gw.write(frame(Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.PING, seq=0)))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(gw.read(), 0.1)


async def test_브로드캐스트는_노드별_슬롯지연_ACK():
    gw = FakeGatewayTransport(slot_ms=30)
    await gw.write(frame(Packet(src=GATEWAY_ID, dst=BROADCAST_ID,
                                type=MsgType.COMMIT, seq=9, payload=b"\x00")))
    srcs = []
    for _ in range(2):
        raw = await asyncio.wait_for(gw.read(), 1.0)
        srcs.append(decode(cobs.decode(raw.rstrip(b"\x00"))).src)
    assert srcs == [0x01, 0x02]      # NodeID×slot 순서


async def test_STATUS_REQ_응답_포맷():
    gw = FakeGatewayTransport()
    resp = await roundtrip(gw, Packet(src=GATEWAY_ID, dst=0x01,
                                      type=MsgType.STATUS_REQ, seq=3))
    assert resp.type == MsgType.STATUS_RES
    batt, last_seq, uptime, err = struct.unpack("<HBHB", resp.payload)
    assert batt == 3900 and err == 0
