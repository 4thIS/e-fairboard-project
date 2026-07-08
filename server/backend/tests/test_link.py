import asyncio

import pytest

from app.protocol.framing import FrameAccumulator, encode_frame
from app.protocol.link import LinkManager, LinkProtocolError, LinkTimeoutError
from app.protocol.packet import (
    AckResult, MsgType, Packet, build_ack, build_pong, decode, encode,
)
from app.transport.virtual import virtual_pair


class FakePeer:
    """transport 반대쪽 끝 — 수신 패킷마다 스크립트된 응답을 보낸다."""

    def __init__(self, transport):
        self.transport = transport
        self.acc = FrameAccumulator()
        self.received: list[Packet] = []
        self.script = []  # 수신 순서대로 소비: "ok"|"drop"|"busy"|"bad_type"|"pong"
        self._task = None

    def start(self):
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            chunk = await self.transport.read()
            for raw in self.acc.feed(chunk):
                pkt = decode(raw)
                self.received.append(pkt)
                action = self.script.pop(0) if self.script else "ok"
                await self._respond(pkt, action)

    async def _respond(self, pkt: Packet, action: str):
        if action == "drop":
            return
        if action == "pong":
            reply = Packet(src=pkt.dst, dst=pkt.src, type=MsgType.PONG, seq=pkt.seq,
                           payload=build_pong(3900, -60, 0))
        else:
            result = {"ok": AckResult.OK, "busy": AckResult.BUSY,
                      "bad_type": AckResult.BAD_TYPE}[action]
            reply = Packet(src=pkt.dst, dst=pkt.src, type=MsgType.ACK, seq=pkt.seq,
                           payload=build_ack(pkt.seq, result))
        await self.transport.write(encode_frame(encode(reply)))

    def stop(self):
        if self._task:
            self._task.cancel()


@pytest.fixture
async def link_and_peer():
    server_side, peer_side = virtual_pair()
    link = LinkManager(server_side, ack_timeout_s=0.05, retries=3)
    await link.start()
    peer = FakePeer(peer_side)
    peer.start()
    yield link, peer
    peer.stop()
    await link.stop()


async def test_request_ok_first_try(link_and_peer):
    link, peer = link_and_peer
    ack = await link.request(0x01, MsgType.SET_TEMPLATE, b"\x00", expect=MsgType.ACK)
    assert ack.type == MsgType.ACK
    assert len(peer.received) == 1


async def test_retry_after_drop_then_success(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["drop", "ok"]
    await link.request(0x01, MsgType.COMMIT, b"\x00", expect=MsgType.ACK)
    assert len(peer.received) == 2
    # 재전송은 동일 SEQ (멱등 재적용 방지의 전제)
    assert peer.received[0].seq == peer.received[1].seq


async def test_all_retries_exhausted_raises_timeout(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["drop", "drop", "drop", "drop"]
    with pytest.raises(LinkTimeoutError):
        await link.request(0x01, MsgType.PING, expect=MsgType.PONG)
    assert len(peer.received) == 4  # 1 + retries(3)


async def test_busy_ack_triggers_retry(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["busy", "ok"]
    await link.request(0x01, MsgType.COMMIT, b"\x01", expect=MsgType.ACK)
    assert len(peer.received) == 2


async def test_bad_type_raises_immediately(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["bad_type"]
    with pytest.raises(LinkProtocolError):
        await link.request(0x01, MsgType.COMMIT, b"\x00", expect=MsgType.ACK)
    assert len(peer.received) == 1


async def test_ping_expects_pong(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["pong"]
    pong = await link.request(0x01, MsgType.PING, expect=MsgType.PONG)
    assert pong.type == MsgType.PONG and pong.src == 0x01


async def test_seq_rollover():
    server_side, _ = virtual_pair()
    link = LinkManager(server_side)
    link._seq = 0xFF
    assert link._next_seq() == 0xFF
    assert link._next_seq() == 0x00
