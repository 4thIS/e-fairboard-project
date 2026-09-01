import pytest

from app.protocol.packet import (
    BROADCAST, FRAG_SINGLE, GATEWAY_ID, MAX_PAYLOAD, VER,
    AckResult, CrcError, MsgType, Packet, PacketError,
    build_ack, build_set_field, build_set_qr, build_status_res,
    decode, encode, parse_ack, parse_status_res,
)


def test_roundtrip_no_payload():
    p = Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.PING, seq=7)
    assert decode(encode(p)) == p


def test_roundtrip_with_payload_and_broadcast():
    p = Packet(src=GATEWAY_ID, dst=BROADCAST, type=MsgType.COMMIT, seq=0xFF,
               payload=b"\x01")
    assert decode(encode(p)) == p


def test_wire_layout_is_7byte_header_le_crc():
    p = Packet(src=0x00, dst=0x02, type=MsgType.SET_TEMPLATE, seq=3,
               payload=b"\x01")
    raw = encode(p)
    assert raw[:7] == bytes([VER, 0x00, 0x02, 0x10, 3, FRAG_SINGLE, 1])
    assert raw[7] == 0x01
    assert len(raw) == 7 + 1 + 2  # 헤더+페이로드+CRC16


def test_corrupted_crc_raises():
    raw = bytearray(encode(Packet(0, 1, MsgType.PING, 0)))
    raw[-1] ^= 0xFF
    with pytest.raises(CrcError):
        decode(bytes(raw))


def test_payload_over_200_rejected():
    with pytest.raises(PacketError):
        encode(Packet(0, 1, MsgType.SET_FIELD, 0, payload=b"x" * (MAX_PAYLOAD + 1)))


def test_short_buffer_rejected():
    with pytest.raises(PacketError):
        decode(b"\x01\x00\x01")


def test_set_field_builder_utf8():
    payload = build_set_field(2, "부스")  # 한글 2자 = 6B
    assert payload[0] == 2 and payload[1] == 6
    assert payload[2:] == "부스".encode("utf-8")


def test_set_qr_builder():
    payload = build_set_qr("https://x.io/a")
    assert payload[0] == 0 and payload[1] == 14


def test_ack_roundtrip():
    assert parse_ack(build_ack(9, AckResult.BUSY)) == (9, AckResult.BUSY)


def test_status_res_little_endian():
    payload = build_status_res(batt_mv=3700, last_seq=5, uptime_s=600, err_cnt=1)
    assert payload[0:2] == (3700).to_bytes(2, "little")
    assert parse_status_res(payload) == (3700, 5, 600, 1)


def test_set_field_fragments():
    from app.protocol.packet import build_set_field_fragments, build_set_field, FRAG_SINGLE

    # 짧은 필드 → 조각 하나, FRAG_SINGLE, 단일 build_set_field 와 동일 payload
    short = build_set_field_fragments(3, "부스")
    assert len(short) == 1
    assert short[0][1] == FRAG_SINGLE
    assert short[0][0] == build_set_field(3, "부스")

    # 긴 필드 → 여러 조각: 인덱스 0..n-1, 마지막만 LAST, chunk_len 정확
    text = "가나다" * 50  # 450B > 198
    frags = build_set_field_fragments(2, text)
    assert len(frags) >= 2
    for i, (payload, frag) in enumerate(frags):
        assert payload[0] == 2                                   # field_id
        assert (frag & 0x7F) == i                                # 인덱스
        assert bool(frag & 0x80) == (i == len(frags) - 1)        # LAST 는 마지막만
        assert payload[1] == len(payload) - 2                    # chunk_len
        payload[2:2 + payload[1]].decode("utf-8")                # 글자 경계 — 단독 디코드 OK

    # 재조립 == 원문
    joined = b"".join(p[2:2 + p[1]] for p, _ in frags)
    assert joined.decode("utf-8") == text
