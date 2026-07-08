import asyncio
import time

from ..protocol.packet import (
    BROADCAST, AckResult, MsgType, Packet,
    build_ack, build_pong, build_status_res,
)

_BROADCAST_ACK_SLOT_S = 0.2  # PROTOCOL.md §5: NodeID×200ms


class VirtualNode:
    """노드 펌웨어와 동일 동작의 상태머신 — 지시서의 스펙이 된다 (스펙 §5.2)."""

    def __init__(self, node_id: int, channel, *, refresh_partial_s: float = 1.0,
                 refresh_full_s: float = 3.0, batt_start_mv: int = 4100,
                 batt_drain_mv_per_min: float = 2.0) -> None:
        self.node_id = node_id
        self._channel = channel
        self._refresh_s = {0: refresh_partial_s, 1: refresh_full_s}
        self._batt_start_mv = batt_start_mv
        self.batt_drain_mv_per_min = batt_drain_mv_per_min
        self._boot_at = time.monotonic()
        self.powered = True
        self.err_cnt = 0
        self.last_seq = 0
        self._last_handled: tuple[int, int] | None = None  # (TYPE, SEQ) 멱등
        self._staged_template: int | None = None
        self._staged_fields: dict[int, str] = {}
        self._staged_qr: str | None = None
        self._template_id: int | None = None
        self._fields: dict[int, str] = {}
        self._qr_url: str | None = None
        self._last_commit_at: float | None = None

    @property
    def batt_mv(self) -> int:
        drained = (time.monotonic() - self._boot_at) / 60 * self.batt_drain_mv_per_min
        return max(3000, int(self._batt_start_mv - drained))

    @property
    def uptime_s(self) -> int:
        return int(time.monotonic() - self._boot_at) & 0xFFFF

    @property
    def display_state(self) -> dict:
        return {
            "template_id": self._template_id,
            "fields": {str(k): v for k, v in self._fields.items()},
            "qr_url": self._qr_url,
            "last_commit_at": self._last_commit_at,
        }

    async def on_air(self, pkt: Packet) -> None:
        if not self.powered:
            return
        if pkt.type in (MsgType.PING, MsgType.STATUS_REQ):
            await self._reply_query(pkt)
            return
        # 멱등: 직전과 동일 (TYPE,SEQ)면 재적용 없이 ACK만 재전송
        if self._last_handled == (pkt.type, pkt.seq):
            await self._ack(pkt, AckResult.OK)
            return
        result = self._apply(pkt)
        if result == AckResult.OK and pkt.type == MsgType.COMMIT:
            await asyncio.sleep(self._refresh_s.get(pkt.payload[0], 1.0))
            self._commit()
        if result == AckResult.OK:
            self._last_handled = (pkt.type, pkt.seq)
            self.last_seq = pkt.seq
        else:
            self.err_cnt += 1
        await self._ack(pkt, result)

    def _apply(self, pkt: Packet) -> AckResult:
        if pkt.type == MsgType.SET_TEMPLATE:
            self._staged_template = pkt.payload[0]
        elif pkt.type == MsgType.SET_FIELD:
            text_len = pkt.payload[1]
            self._staged_fields[pkt.payload[0]] = pkt.payload[2:2 + text_len].decode("utf-8")
        elif pkt.type == MsgType.SET_QR:
            url_len = pkt.payload[1]
            self._staged_qr = pkt.payload[2:2 + url_len].decode("utf-8")
        elif pkt.type == MsgType.COMMIT:
            pass  # 반영은 on_air에서 갱신 지연 후
        else:
            return AckResult.BAD_TYPE
        return AckResult.OK

    def _commit(self) -> None:
        if self._staged_template is not None:
            self._template_id = self._staged_template
        self._fields.update(self._staged_fields)
        if self._staged_qr is not None:
            self._qr_url = self._staged_qr
        self._staged_fields = {}
        self._staged_qr = None
        self._staged_template = None
        self._last_commit_at = time.time()

    async def _ack(self, pkt: Packet, result: AckResult) -> None:
        if pkt.dst == BROADCAST:
            await asyncio.sleep(self.node_id * _BROADCAST_ACK_SLOT_S)
        await self._channel.transmit(Packet(
            self.node_id, pkt.src, MsgType.ACK, pkt.seq,
            build_ack(pkt.seq, result)))

    async def _reply_query(self, pkt: Packet) -> None:
        if pkt.type == MsgType.PING:
            payload = build_pong(self.batt_mv, -60, 0)
            reply_type = MsgType.PONG
        else:
            payload = build_status_res(self.batt_mv, self.last_seq,
                                       self.uptime_s, self.err_cnt)
            reply_type = MsgType.STATUS_RES
        await self._channel.transmit(Packet(
            self.node_id, pkt.src, reply_type, pkt.seq, payload))
