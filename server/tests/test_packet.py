import pytest

from app.protocol.const import MsgType
from app.protocol.packet import MAX_PAYLOAD, Packet, PacketError, decode


def test_빈_페이로드_인코딩은_9바이트():
    pkt = Packet(src=0x00, dst=0x01, type=MsgType.PING, seq=0)
    raw = pkt.encode()
    assert len(raw) == 9
    assert raw[:7] == bytes([0x01, 0x00, 0x01, 0x01, 0x00, 0x80, 0x00])


def test_encode_decode_왕복():
    pkt = Packet(src=0x00, dst=0x02, type=MsgType.SET_FIELD, seq=0x7F,
                 payload=bytes([0, 5]) + "제목".encode())
    assert decode(pkt.encode()) == pkt


def test_최대_페이로드_200B_왕복과_초과_거부():
    ok = Packet(src=0, dst=1, type=MsgType.SET_FIELD, seq=1, payload=b"x" * MAX_PAYLOAD)
    assert decode(ok.encode()).payload == b"x" * MAX_PAYLOAD
    with pytest.raises(PacketError):
        Packet(src=0, dst=1, type=MsgType.SET_FIELD, seq=1,
               payload=b"x" * (MAX_PAYLOAD + 1)).encode()


def test_CRC_오염시_PacketError():
    raw = bytearray(Packet(src=0, dst=1, type=MsgType.PING, seq=3).encode())
    raw[-1] ^= 0xFF
    with pytest.raises(PacketError, match="CRC"):
        decode(bytes(raw))


def test_LEN_불일치_및_짧은_프레임_거부():
    with pytest.raises(PacketError):
        decode(b"\x01\x00\x01")
    raw = bytearray(Packet(src=0, dst=1, type=MsgType.PING, seq=0).encode())
    raw[6] = 5  # LEN 조작
    with pytest.raises(PacketError):
        decode(bytes(raw))


def test_지원하지_않는_VER_거부():
    raw = bytearray(Packet(src=0, dst=1, type=MsgType.PING, seq=0).encode())
    raw[0] = 0x02
    with pytest.raises(PacketError, match="VER"):
        decode(bytes(raw))
