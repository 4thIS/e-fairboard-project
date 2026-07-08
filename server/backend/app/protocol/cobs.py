class CobsError(Exception):
    pass


def cobs_encode(data: bytes) -> bytes:
    out = bytearray([0])  # 첫 코드 바이트 자리
    code_index = 0
    code = 1
    for byte in data:
        if byte == 0:
            out[code_index] = code
            code_index = len(out)
            out.append(0)
            code = 1
        else:
            out.append(byte)
            code += 1
            if code == 0xFF:  # 254 논제로 블록 꽉 참 → 그룹 분할
                out[code_index] = code
                code_index = len(out)
                out.append(0)
                code = 1
    out[code_index] = code
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        code = data[i]
        if code == 0:
            raise CobsError("encoded stream contains zero byte")
        block = data[i + 1 : i + code]
        if len(block) != code - 1:
            raise CobsError("truncated block")
        if 0 in block:  # 유효한 COBS 스트림에는 0x00이 없음
            raise CobsError("encoded stream contains zero byte")
        out += block
        i += code
        if code != 0xFF and i < len(data):
            out.append(0)
    return bytes(out)
