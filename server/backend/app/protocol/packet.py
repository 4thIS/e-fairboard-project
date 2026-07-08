from dataclasses import dataclass, field
from enum import IntEnum

from .crc16 import crc16_ccitt

VER = 0x01
GATEWAY_ID = 0x00
BROADCAST = 0xFF
FRAG_SINGLE = 0x80  # bit7=LAST, 인덱스 0
MAX_PAYLOAD = 200
_HEADER_LEN = 7
_CRC_LEN = 2


class MsgType(IntEnum):
    PING = 0x01
    PONG = 0x02
    SET_TEMPLATE = 0x10
    SET_FIELD = 0x11
    SET_QR = 0x12
    COMMIT = 0x13
    IMG_FRAG = 0x14
    ACK = 0x20
    STATUS_REQ = 0x30
    STATUS_RES = 0x31


class AckResult(IntEnum):
    OK = 0
    CRC_FAIL = 1
    BUSY = 2
    BAD_TYPE = 3


class PacketError(Exception):
    pass


class CrcError(PacketError):
    pass


@dataclass(frozen=True)
class Packet:
    src: int
    dst: int
    type: MsgType
    seq: int
    payload: bytes = field(default=b"")
    frag: int = FRAG_SINGLE
    ver: int = VER


def encode(p: Packet) -> bytes:
    if len(p.payload) > MAX_PAYLOAD:
        raise PacketError(f"payload {len(p.payload)}B > {MAX_PAYLOAD}B")
    body = bytes([p.ver, p.src, p.dst, p.type, p.seq, p.frag, len(p.payload)]) + p.payload
    return body + crc16_ccitt(body).to_bytes(_CRC_LEN, "little")


def decode(buf: bytes) -> Packet:
    if len(buf) < _HEADER_LEN + _CRC_LEN:
        raise PacketError("buffer too short")
    length = buf[6]
    if len(buf) != _HEADER_LEN + length + _CRC_LEN:
        raise PacketError("LEN mismatch")
    body, crc = buf[:-_CRC_LEN], int.from_bytes(buf[-_CRC_LEN:], "little")
    if crc16_ccitt(body) != crc:
        raise CrcError("CRC16 mismatch")
    try:
        msg_type = MsgType(buf[3])
    except ValueError as exc:
        raise PacketError(f"unknown TYPE 0x{buf[3]:02X}") from exc
    return Packet(src=buf[1], dst=buf[2], type=msg_type, seq=buf[4],
                  payload=bytes(buf[7:-_CRC_LEN]), frag=buf[5], ver=buf[0])


# ---- 페이로드 빌더/파서 (PROTOCOL.md §3) ----

def build_set_field(field_id: int, text: str) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) > MAX_PAYLOAD - 2:
        raise PacketError("field text too long")
    return bytes([field_id, len(raw)]) + raw


def build_set_qr(url: str, qr_slot: int = 0) -> bytes:
    raw = url.encode("utf-8")
    if len(raw) > MAX_PAYLOAD - 2:
        raise PacketError("qr url too long")
    return bytes([qr_slot, len(raw)]) + raw


def build_ack(ack_seq: int, result: AckResult) -> bytes:
    return bytes([ack_seq, result])


def parse_ack(payload: bytes) -> tuple[int, AckResult]:
    return payload[0], AckResult(payload[1])


def build_pong(batt_mv: int, rssi: int, status: int) -> bytes:
    return batt_mv.to_bytes(2, "little") + rssi.to_bytes(1, "little", signed=True) \
        + bytes([status])


def parse_pong(payload: bytes) -> tuple[int, int, int]:
    return (int.from_bytes(payload[0:2], "little"),
            int.from_bytes(payload[2:3], "little", signed=True), payload[3])


def build_status_res(batt_mv: int, last_seq: int, uptime_s: int, err_cnt: int) -> bytes:
    return (batt_mv.to_bytes(2, "little") + bytes([last_seq])
            + uptime_s.to_bytes(2, "little") + bytes([err_cnt]))


def parse_status_res(payload: bytes) -> tuple[int, int, int, int]:
    return (int.from_bytes(payload[0:2], "little"), payload[2],
            int.from_bytes(payload[3:5], "little"), payload[5])
