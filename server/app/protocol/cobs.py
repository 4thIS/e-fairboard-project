"""COBS(Consistent Overhead Byte Stuffing) — 프레임 구분자 0x00 제거용 (PROTOCOL §7)."""


class CobsError(ValueError):
    """COBS 디코딩 실패."""


def encode(data: bytes) -> bytes:
    out = bytearray()
    block = bytearray()
    for b in data:
        if b == 0:
            out.append(len(block) + 1)
            out += block
            block.clear()
        else:
            block.append(b)
            if len(block) == 254:
                out.append(0xFF)
                out += block
                block.clear()
    out.append(len(block) + 1)
    out += block
    return bytes(out)


def decode(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        code = data[i]
        if code == 0:
            raise CobsError("encoded data contains 0x00")
        if i + code > len(data):
            raise CobsError(f"block overruns input: code={code} at {i}")
        out += data[i + 1:i + code]
        i += code
        if code < 0xFF and i < len(data):
            out.append(0)
    return bytes(out)
