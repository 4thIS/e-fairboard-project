"""SerialTransport — pyserial 'loop://' 루프백으로 하드웨어 없이 검증.
쓴 바이트가 그대로 읽히고, 프레이밍 스택으로 원본 패킷이 복원되는지 본다."""
import asyncio

from app.protocol.framing import FrameAccumulator, encode_frame
from app.transport.serial import SerialTransport


async def _read_until_frame(t: SerialTransport, acc: FrameAccumulator, tries=50):
    frames: list[bytes] = []
    for _ in range(tries):
        frames += acc.feed(await t.read())
        if frames:
            return frames
    return frames


async def test_loopback_roundtrip_recovers_packet():
    t = SerialTransport("loop://", 9600)
    try:
        payload = b"\x00\x01\x02\xffhello"  # 0x00 포함 — COBS가 프레임 경계와 안 겹치게
        await t.write(encode_frame(payload))
        frames = await _read_until_frame(t, FrameAccumulator())
        assert frames and frames[0] == payload
    finally:
        await t.close()


async def test_idle_read_returns_empty_not_blocks():
    t = SerialTransport("loop://", 9600)
    try:
        # 아무것도 안 썼을 때 read 가 b'' 로 곧 돌아와야 한다(무한 블록 금지).
        got = await asyncio.wait_for(t.read(), timeout=1.0)
        assert got == b""
    finally:
        await t.close()
