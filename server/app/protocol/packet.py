"""논리 패킷 코덱 (PROTOCOL.md §2). 순수 함수 — 시리얼·asyncio 무관."""
from __future__ import annotations

import struct
from dataclasses import dataclass

from app.protocol.const import VER_V1

HEADER_LEN = 7   # VER SRC DST TYPE SEQ FRAG LEN (PROTOCOL §2 필드 표 기준)
CRC_LEN = 2      # CRC16 little-endian
MAX_PAYLOAD = 200


class PacketError(ValueError):
    """프레임 디코딩 실패 (길이·버전·CRC 불일치)."""


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflect, xorout 0."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


@dataclass(frozen=True)
class Packet:
    src: int
    dst: int
    type: int
    seq: int
    frag: int = 0x80          # bit7=LAST, 단일 패킷 = 0x80
    payload: bytes = b""
    ver: int = VER_V1

    def encode(self) -> bytes:
        if len(self.payload) > MAX_PAYLOAD:
            raise PacketError(f"payload {len(self.payload)}B > {MAX_PAYLOAD}B")
        body = bytes([self.ver, self.src, self.dst, self.type,
                      self.seq, self.frag, len(self.payload)]) + self.payload
        return body + struct.pack("<H", crc16_ccitt(body))


def decode(raw: bytes) -> Packet:
    if len(raw) < HEADER_LEN + CRC_LEN:
        raise PacketError(f"frame too short: {len(raw)}B")
    ver, src, dst, typ, seq, frag, length = raw[:HEADER_LEN]
    if ver != VER_V1:
        raise PacketError(f"unsupported VER 0x{ver:02X}")
    if len(raw) != HEADER_LEN + length + CRC_LEN:
        raise PacketError(f"LEN mismatch: LEN={length}, frame={len(raw)}B")
    body = raw[:HEADER_LEN + length]
    (crc,) = struct.unpack("<H", raw[HEADER_LEN + length:])
    if crc != crc16_ccitt(body):
        raise PacketError("CRC mismatch")
    return Packet(src=src, dst=dst, type=typ, seq=seq, frag=frag,
                  payload=bytes(raw[HEADER_LEN:HEADER_LEN + length]), ver=ver)
