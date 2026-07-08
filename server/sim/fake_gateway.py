"""모의 게이트웨이: 실물 하드웨어 없이 서버 E2E 개발·시연용.

GW=투명 릴레이 가정(스펙 §8.1) — 서버 프레임을 가상 노드 상태머신에 전달하고
노드 응답을 그대로 프레이밍해 돌려준다. LoRa 전파·재전송은 모사하지 않는다.
"""
from __future__ import annotations

import asyncio
import struct
import time

from app.bridge.transport import Transport
from app.protocol import cobs
from app.protocol.const import BROADCAST_ID, GATEWAY_ID, AckResult, MsgType
from app.protocol.packet import Packet, decode


class VirtualNode:
    def __init__(self, node_id: int, batt_mv: int = 3900, rssi: int = -60):
        self.node_id = node_id
        self.batt_mv = batt_mv
        self.rssi = rssi
        self.template_id: int | None = None
        self.staging: dict[int, str] = {}
        self.committed: dict[int, str] = {}
        self.qr: dict[int, str] = {}
        self.last_refresh: int | None = None
        self.silent = False                     # 실패 주입: 무응답
        self.err_cnt = 0
        self._last: tuple[int, int] | None = None   # (TYPE, SEQ) 중복 검출
        self._last_resp: Packet | None = None
        self._boot = time.monotonic()

    def handle(self, pkt: Packet) -> Packet | None:
        if self.silent:
            return None
        if self._last == (pkt.type, pkt.seq) and self._last_resp is not None:
            return self._last_resp              # 멱등: 재적용 없이 응답만 재전송
        resp = self._process(pkt)
        self._last = (pkt.type, pkt.seq)
        self._last_resp = resp
        return resp

    def _ack(self, pkt: Packet, result: AckResult = AckResult.OK) -> Packet:
        return Packet(src=self.node_id, dst=GATEWAY_ID, type=MsgType.ACK,
                      seq=pkt.seq, payload=bytes([pkt.seq, result]))

    def _process(self, pkt: Packet) -> Packet:
        t = pkt.type
        if t == MsgType.PING:
            return Packet(src=self.node_id, dst=GATEWAY_ID, type=MsgType.PONG,
                          seq=pkt.seq,
                          payload=struct.pack("<Hb", self.batt_mv, self.rssi) + b"\x00")
        if t == MsgType.SET_TEMPLATE:
            self.template_id = pkt.payload[0]
            self.staging.clear()
            return self._ack(pkt)
        if t == MsgType.SET_FIELD:
            fid, ln = pkt.payload[0], pkt.payload[1]
            self.staging[fid] = pkt.payload[2:2 + ln].decode()
            return self._ack(pkt)
        if t == MsgType.SET_QR:
            slot, ln = pkt.payload[0], pkt.payload[1]
            self.qr[slot] = pkt.payload[2:2 + ln].decode()
            return self._ack(pkt)
        if t == MsgType.COMMIT:
            self.committed = dict(self.staging)
            self.last_refresh = pkt.payload[0]
            return self._ack(pkt)
        if t == MsgType.STATUS_REQ:
            uptime = int(time.monotonic() - self._boot) & 0xFFFF
            last_seq = self._last[1] if self._last else 0
            return Packet(src=self.node_id, dst=GATEWAY_ID, type=MsgType.STATUS_RES,
                          seq=pkt.seq,
                          payload=struct.pack("<HBHB", self.batt_mv, last_seq,
                                              uptime, self.err_cnt))
        self.err_cnt += 1
        return self._ack(pkt, AckResult.BAD_TYPE)


class FakeGatewayTransport(Transport):
    def __init__(self, nodes: dict[int, VirtualNode] | None = None, *,
                 slot_ms: int = 0, latency: float = 0.0):
        self.nodes = nodes if nodes is not None else {
            0x01: VirtualNode(0x01), 0x02: VirtualNode(0x02)}
        self._rx: asyncio.Queue[bytes] = asyncio.Queue()
        self._buf = bytearray()
        self._slot = slot_ms / 1000
        self._latency = latency

    async def open(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def read(self) -> bytes:
        return await self._rx.get()

    async def write(self, data: bytes) -> None:
        self._buf += data
        while (i := self._buf.find(0)) != -1:
            raw = bytes(self._buf[:i])
            del self._buf[:i + 1]
            if raw:
                self._route(decode(cobs.decode(raw)))

    def _route(self, pkt: Packet) -> None:
        if pkt.dst == BROADCAST_ID:
            targets = [self.nodes[k] for k in sorted(self.nodes)]
        else:
            node = self.nodes.get(pkt.dst)
            targets = [node] if node else []
        for node in targets:
            resp = node.handle(pkt)
            if resp is None:
                continue
            delay = self._latency
            if pkt.dst == BROADCAST_ID:
                delay += node.node_id * self._slot   # §5 ACK 슬롯
            payload = cobs.encode(resp.encode()) + b"\x00"
            if delay > 0:
                asyncio.get_running_loop().call_later(
                    delay, self._rx.put_nowait, payload)
            else:
                self._rx.put_nowait(payload)
