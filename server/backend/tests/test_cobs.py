import pytest

from app.protocol.cobs import CobsError, cobs_decode, cobs_encode


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\x00",
        b"\x11\x22\x00\x33",
        b"\x11\x00\x00\x00",
        b"hello world",
        bytes(range(1, 255)),      # 254 논제로 — 0xFF 블록 경계
        bytes(range(256)) * 3,     # 0 포함 장문
    ],
)
def test_roundtrip(raw):
    encoded = cobs_encode(raw)
    assert b"\x00" not in encoded
    assert cobs_decode(encoded) == raw


def test_known_vector_simple():
    # 고전 벡터: 11 22 00 33 -> 03 11 22 02 33
    assert cobs_encode(b"\x11\x22\x00\x33") == b"\x03\x11\x22\x02\x33"


def test_decode_rejects_embedded_zero():
    with pytest.raises(CobsError):
        cobs_decode(b"\x03\x11\x00")


def test_decode_rejects_truncated_block():
    with pytest.raises(CobsError):
        cobs_decode(b"\x05\x11\x22")
