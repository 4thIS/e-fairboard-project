def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE — PROTOCOL.md §2: poly=0x1021, init=0xFFFF, no reflect."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc
