from app.protocol.crc16 import crc16_ccitt


def test_known_vector_123456789():
    # CRC-16/CCITT-FALSE 표준 체크값
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_empty_input_is_init_value():
    assert crc16_ccitt(b"") == 0xFFFF


def test_single_zero_byte():
    assert crc16_ccitt(b"\x00") == 0xE1F0


def test_result_fits_16_bits():
    assert 0 <= crc16_ccitt(bytes(range(256))) <= 0xFFFF
