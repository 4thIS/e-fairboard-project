from app.protocol.packet import crc16_ccitt


def test_crc16_ccitt_false_표준벡터():
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_crc16_빈입력은_init값():
    assert crc16_ccitt(b"") == 0xFFFF


def test_crc16_한바이트_변조시_달라짐():
    assert crc16_ccitt(b"\x01\x02\x03") != crc16_ccitt(b"\x01\x02\x02")
