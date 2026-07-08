"""서버↔게이트웨이 링크: COBS 프레이밍, 노드별 SEQ, 요청-응답 매칭 (PROTOCOL §5·7)."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Callable

from app.bridge.transport import Transport
from app.protocol import cobs
from app.protocol.const import MsgType
from app.protocol.packet import Packet, PacketError, decode

log = logging.getLogger(__name__)
FRAME_DELIM = b"\x00"


class LinkTimeout(TimeoutError):
    """응답 타임아웃 — 상위(deploy)에서 재시도·OFFLINE 판단."""


class GatewayLink:
    def __init__(self, transport: Transport, *, timeout: float = 6.0,
                 on_event: Callable[[Packet], None] | None = None):
        self._t = transport
        self._timeout = timeout
        self._on_event = on_event
        self._seq: dict[int, int] = defaultdict(lambda: -1)
        # (src_node, expect_type) -> (expected_ack_seq | None, Future)
        self._pending: dict[tuple[int, int], tuple[int | None, asyncio.Future]] = {}
        self._buf = bytearray()
        self._reader: asyncio.Task | None = None
        self.rx_dropped = 0

    def next_seq(self, dst: int) -> int:
        self._seq[dst] = (self._seq[dst] + 1) & 0xFF
        return self._seq[dst]

    async def start(self) -> None:
        await self._t.open()
        self._reader = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
            self._reader = None
        await self._t.close()

    async def send(self, pkt: Packet) -> None:
        await self._t.write(cobs.encode(pkt.encode()) + FRAME_DELIM)

    async def request(self, pkt: Packet, expect: MsgType,
                      timeout: float | None = None) -> Packet:
        key = (pkt.dst, int(expect))
        exp_seq = pkt.seq if expect is MsgType.ACK else None
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[key] = (exp_seq, fut)
        try:
            await self.send(pkt)
            return await asyncio.wait_for(fut, timeout or self._timeout)
        except asyncio.TimeoutError:
            raise LinkTimeout(
                f"node 0x{pkt.dst:02X} {expect.name} 응답 없음") from None
        finally:
            self._pending.pop(key, None)

    async def _read_loop(self) -> None:
        backoff = 1.0
        while True:
            try:
                chunk = await self._t.read()
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as e:                    # 시리얼 단절 등
                log.warning("transport read 실패, %.0fs 후 재연결: %s", backoff, e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                try:
                    await self._t.close()
                    await self._t.open()
                except Exception as e2:
                    log.warning("재연결 실패: %s", e2)
                continue
            if not chunk:
                continue
            self._buf += chunk
            while (i := self._buf.find(0)) != -1:
                raw = bytes(self._buf[:i])
                del self._buf[:i + 1]
                if not raw:
                    continue
                try:
                    pkt = decode(cobs.decode(raw))
                except (PacketError, cobs.CobsError) as e:
                    self.rx_dropped += 1
                    log.warning("프레임 폐기(%d): %s", self.rx_dropped, e)
                    continue
                self._dispatch(pkt)

    def _dispatch(self, pkt: Packet) -> None:
        entry = self._pending.get((pkt.src, pkt.type))
        if entry:
            exp_seq, fut = entry
            matched = exp_seq is None or (pkt.payload and pkt.payload[0] == exp_seq)
            if matched and not fut.done():
                fut.set_result(pkt)
                return
        if self._on_event:
            self._on_event(pkt)
