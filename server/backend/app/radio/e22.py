"""E22-900T22S(SX1262) 설정 순수 로직 — 하드웨어 무관, 테스트 가능.

설정 모드(M1 점퍼 빼기=HIGH, M0 꽂기=LOW)에서 UART 9600 고정으로
`C1`(읽기)/`C0`(쓰기) 명령에 응답한다. 레지스터 9바이트 배치:

    [ADDH, ADDL, NETID, REG0, REG1, CH, REG2, CRYPT_H, CRYPT_L]

이 도구는 **주파수(채널 바이트)만** 바꾼다. freq(MHz) = BASE_MHZ + channel.
실측 골든벡터: `00 00 00 62 E0 12 43 00 00` → ch18 = 868MHz(공장기본, EU).
"""

BASE_MHZ = 850.125  # E22-900: freq = 850.125 + channel (EBYTE 데이터시트)
CH_MIN = 0
CH_MAX = 80         # E22-900 채널 범위 → freq 850.125 ~ 930.125
HW_MIN = 850        # 표시용 하한
HW_MAX = 930        # 표시용 상한
KR920 = (920.9, 923.3)  # 국내 920MHz ISM 대역(권장 범위)

_CH = 5  # 9바이트 레지스터에서 채널 바이트 위치

# REG0(바이트3): bit7-5 UART, bit2-0 공중속도
_UART = {0x00: 1200, 0x20: 2400, 0x40: 4800, 0x60: 9600,
         0x80: 19200, 0xA0: 38400, 0xC0: 57600, 0xE0: 115200}
_AIR = {0x00: 300, 0x01: 1200, 0x02: 2400, 0x03: 4800,
        0x04: 9600, 0x05: 19200, 0x06: 38400, 0x07: 62500}
# REG1(바이트4): bit7-6 서브패킷, bit1-0 송신출력
_SUBPACKET = {0x00: 240, 0x40: 128, 0x80: 64, 0xC0: 32}
_POWER = {0x00: 22, 0x01: 17, 0x02: 13, 0x03: 10}


def channel_to_mhz(ch: int) -> float:
    return round(BASE_MHZ + ch, 3)


def mhz_to_channel(mhz: float) -> int:
    # 채널은 정수 → 입력 MHz 를 가장 가까운 채널로 반올림 (예: 922.125·922 둘 다 채널 72)
    return round(mhz - BASE_MHZ)


def build_read_cmd() -> bytes:
    """레지스터 9개 읽기: C1 <start=00> <len=09>."""
    return bytes([0xC1, 0x00, 0x09])


def build_write_cmd(current9: bytes, mhz: int) -> bytes:
    """현재 레지스터에서 **채널 바이트만** 교체한 쓰기 명령 C0 00 09 + 9B.

    나머지 레지스터(주소·속도·출력·옵션)는 현재값을 그대로 보존한다.
    """
    if len(current9) != 9:
        raise ValueError(f"current registers must be 9 bytes, got {len(current9)}")
    reg = bytearray(current9)
    reg[_CH] = mhz_to_channel(mhz)
    return bytes([0xC0, 0x00, 0x09]) + bytes(reg)


def decode_registers(nine: bytes) -> dict:
    """레지스터 9바이트 → 사람이 읽는 필드값."""
    if len(nine) != 9:
        raise ValueError(f"expected 9 register bytes, got {len(nine)}")
    ch = nine[_CH]
    return {
        "address": (nine[0] << 8) | nine[1],
        "netid": nine[2],
        "uart_bps": _UART.get(nine[3] & 0xE0),
        "air_bps": _AIR.get(nine[3] & 0x07),
        "channel": ch,
        "freq_mhz": channel_to_mhz(ch),
        "subpacket_bytes": _SUBPACKET.get(nine[4] & 0xC0),
        "power_dbm": _POWER.get(nine[4] & 0x03),
        "raw": nine.hex(),
    }


def in_kr920(mhz: float) -> bool:
    return KR920[0] <= mhz <= KR920[1]


if __name__ == "__main__":  # 골든벡터 셀프체크
    gv = bytes.fromhex("000000" "62E0" "12" "43" "0000")  # 실측 공장기본
    assert channel_to_mhz(18) == 868.125 and channel_to_mhz(72) == 922.125
    assert mhz_to_channel(922.125) == 72 and mhz_to_channel(868.125) == 18
    assert mhz_to_channel(922) == 72  # 정수 입력도 가장 가까운 채널로
    d = decode_registers(gv)
    assert d["channel"] == 18 and d["freq_mhz"] == 868.125, d
    assert d["uart_bps"] == 9600 and d["air_bps"] == 2400, d
    assert d["power_dbm"] == 22, d
    # 채널만 바뀌고 나머지 보존
    w = build_write_cmd(gv, 922)
    assert w[:3] == bytes([0xC0, 0x00, 0x09])
    assert w[3 + _CH] == 72
    assert w[3:3 + _CH] == gv[:_CH] and w[3 + _CH + 1:] == gv[_CH + 1:]
    assert not in_kr920(868.125) and in_kr920(922.125)
    print("e22 self-check OK")
