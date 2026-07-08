"""PROTOCOL.md §3 상수. 펌웨어(gateway/node)와 값 동기화 필수."""
from enum import IntEnum

VER_V1 = 0x01
GATEWAY_ID = 0x00
BROADCAST_ID = 0xFF


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
