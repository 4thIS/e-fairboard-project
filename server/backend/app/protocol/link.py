import asyncio

from ..transport.base import Transport
from .framing import FrameAccumulator, encode_frame
from .packet import (
    BROADCAST, GATEWAY_ID, AckResult, MsgType, Packet, PacketError, decode, encode, parse_ack,
)

_BUSY_BACKOFF_S = 0.3


class LinkError(Exception):
    pass


class LinkTimeoutError(LinkError):
    pass


class LinkProtocolError(LinkError):
    pass


class LinkManager:
    """stop-and-wait 신뢰 전송 (PROTOCOL.md §5). 요청은 Lock으로 직렬화."""

    def __init__(self, transport: Transport, *, ack_timeout_s: float = 1.5,
                 retries: int = 3, src: int = GATEWAY_ID,
                 commit_ack_timeout_s: float | None = None) -> None:
        self._transport = transport
        self._ack_timeout_s = ack_timeout_s
        # COMMIT 은 노드가 e-Paper 렌더(7.5" 3색 = 15~20초) 뒤에 ACK 하므로 훨씬 길게 기다린다.
        # None 이면 ack_timeout_s 와 동일 (가상 모드는 렌더가 즉시라 무관).
        self._commit_ack_timeout_s = commit_ack_timeout_s or ack_timeout_s
        self._retries = retries
        self._src = src
        self._seq = 0
        self._lock = asyncio.Lock()
        self._acc = FrameAccumulator()
        self._inbox: asyncio.Queue[Packet] = asyncio.Queue()
        self._reader: asyncio.Task | None = None

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq = (self._seq + 1) & 0xFF
        return seq

    async def start(self) -> None:
        self._reader = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
        await self._transport.close()

    async def _read_loop(self) -> None:
        while True:
            chunk = await self._transport.read()
            for raw in self._acc.feed(chunk):
                try:
                    self._inbox.put_nowait(decode(raw))
                except PacketError:
                    continue  # 깨진 패킷 폐기 — 송신측 타임아웃이 재전송

    def _drain_inbox(self) -> None:
        while not self._inbox.empty():
            self._inbox.get_nowait()

    async def request(self, dst: int, type_: MsgType, payload: bytes = b"", *,
                      expect: MsgType) -> Packet:
        async with self._lock:
            seq = self._next_seq()
            frame = encode_frame(encode(Packet(self._src, dst, type_, seq, payload)))
            timeout = (self._commit_ack_timeout_s if type_ == MsgType.COMMIT
                       else self._ack_timeout_s)
            attempts = 1 + self._retries
            for _ in range(attempts):
                self._drain_inbox()  # 이전 시도의 뒤늦은 응답 제거
                await self._transport.write(frame)
                try:
                    reply = await self._wait_reply(dst, seq, expect, timeout)
                except LinkTimeoutError:
                    continue
                if reply is not None:
                    return reply
                await asyncio.sleep(_BUSY_BACKOFF_S)  # BUSY → 대기 후 재전송
            raise LinkTimeoutError(
                f"no valid reply from 0x{dst:02X} after {attempts} attempts")

    async def broadcast(self, type_: MsgType, payload: bytes = b"", *,
                        repeat: int = 3, gap_s: float = 0.3) -> None:
        """ACK 없는 브로드캐스트(dst=0xFF). 모든 노드가 동시에 받는다.
        수신 확인이 불가하므로 신뢰성 위해 repeat 회 재전송한다 (PROTOCOL.md §5 브로드캐스트)."""
        async with self._lock:
            for i in range(repeat):
                seq = self._next_seq()
                frame = encode_frame(encode(Packet(self._src, BROADCAST, type_, seq, payload)))
                await self._transport.write(frame)
                if i + 1 < repeat:
                    await asyncio.sleep(gap_s)

    async def _wait_reply(self, dst: int, seq: int, expect: MsgType,
                          timeout: float) -> Packet | None:
        """성공 시 Packet, BUSY면 None(재시도 신호), 타임아웃이면 예외."""
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise LinkTimeoutError("ack timeout")
            try:
                pkt = await asyncio.wait_for(self._inbox.get(), timeout=remaining)
            except asyncio.TimeoutError:
                # asyncio.TimeoutError 로 잡아야 한다 — 3.11 부터만 builtin TimeoutError 의
                # 별칭이고, 3.10 에서는 별개 클래스라 `except TimeoutError` 가 못 잡는다.
                # 못 잡으면 재전송이 통째로 죽고 배포 태스크가 그대로 터진다.
                raise LinkTimeoutError("ack timeout") from None
            if pkt.src != dst:
                continue
            if expect == MsgType.ACK and pkt.type == MsgType.ACK:
                ack_seq, result = parse_ack(pkt.payload)
                if ack_seq != seq:
                    continue
                if result == AckResult.OK:
                    return pkt
                if result == AckResult.BAD_TYPE:
                    raise LinkProtocolError("node replied BAD_TYPE")
                return None  # CRC_FAIL·BUSY → 재시도
            if pkt.type == expect:
                return pkt
