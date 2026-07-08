from .cobs import CobsError, cobs_decode, cobs_encode


def encode_frame(packet_bytes: bytes) -> bytes:
    return cobs_encode(packet_bytes) + b"\x00"


class FrameAccumulator:
    """바이트 스트림에서 0x00 구분 COBS 프레임을 분리한다 (PROTOCOL.md §7)."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        self._buf += chunk
        frames: list[bytes] = []
        while (sep := self._buf.find(0)) != -1:
            raw = bytes(self._buf[:sep])
            del self._buf[: sep + 1]
            if not raw:
                continue
            try:
                frames.append(cobs_decode(raw))
            except CobsError:
                continue  # 깨진 프레임 폐기 — 상위 CRC가 최종 방어선
        return frames
