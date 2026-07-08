import pytest

from app.protocol import cobs


@pytest.mark.parametrize("plain,encoded", [
    (b"", b"\x01"),
    (b"\x00", b"\x01\x01"),
    (b"\x00\x00", b"\x01\x01\x01"),
    (b"\x11\x22\x00\x33", b"\x03\x11\x22\x02\x33"),
    (b"\x11\x22\x33\x44", b"\x05\x11\x22\x33\x44"),
])
def test_표준_벡터(plain, encoded):
    assert cobs.encode(plain) == encoded
    assert cobs.decode(encoded) == plain


def test_인코딩_결과에_0x00_없음():
    data = bytes(range(256)) * 2
    assert b"\x00" not in cobs.encode(data)


def test_긴_데이터_왕복_254_255_경계_포함():
    for n in (253, 254, 255, 256, 500):
        data = bytes((i % 255) + 1 for i in range(n))  # 0x00 없는 데이터
        assert cobs.decode(cobs.encode(data)) == data
        with_zeros = bytes(i % 256 for i in range(n))   # 0x00 포함
        assert cobs.decode(cobs.encode(with_zeros)) == with_zeros


def test_손상된_입력_거부():
    with pytest.raises(cobs.CobsError):
        cobs.decode(b"\x05\x11")      # 코드가 남은 길이보다 큼
    with pytest.raises(cobs.CobsError):
        cobs.decode(b"\x00\x01")      # 인코딩 결과에 0x00 불가
