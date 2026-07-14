"""서버의 프로토콜 레퍼런스 구현에서 실제 바이트를 뽑아 C++ 골든 벡터 헤더를 생성한다.

서버 코드(server/backend/app/protocol)는 읽기만 한다. 손으로 옮겨 적은 상수가 아니라
서버가 실제로 내보내는 바이트여야 와이어 포맷 불일치가 테스트에서 잡힌다.

실행: ~/venv/bin/python tools/gen_test_vectors.py
출력: shared/test/golden_vectors.h
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server" / "backend"))

from app.protocol.cobs import cobs_encode
from app.protocol.crc16 import crc16_ccitt
from app.protocol.framing import encode_frame
from app.protocol.packet import (
    AckResult,
    MsgType,
    Packet,
    build_ack,
    build_pong,
    build_set_field,
    build_set_qr,
    build_status_res,
    encode,
)

OUT = ROOT / "shared" / "test" / "golden_vectors.h"


def c_bytes(data: bytes) -> str:
    return "{" + ", ".join(f"0x{b:02X}" for b in data) + "}" if data else "{0}"


def emit_bytes(lines: list[str], name: str, data: bytes) -> None:
    lines.append(f"constexpr uint8_t {name}[] = {c_bytes(data)};")
    lines.append(f"constexpr size_t {name}_LEN = {len(data)};")


def main() -> None:
    lines: list[str] = [
        "// 자동 생성 — 수정하지 말 것. tools/gen_test_vectors.py 로 재생성한다.",
        "// 원본: server/backend/app/protocol (우진 작성 레퍼런스 구현)",
        "#pragma once",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        "namespace golden {",
        "",
        "// ---- CRC-16/CCITT-FALSE ----",
    ]

    crc_cases = [b"123456789", b"", b"\x00", bytes(range(256))]
    lines.append(f"constexpr size_t CRC_CASE_COUNT = {len(crc_cases)};")
    for i, data in enumerate(crc_cases):
        emit_bytes(lines, f"CRC_IN_{i}", data)
        lines.append(f"constexpr uint16_t CRC_OUT_{i} = 0x{crc16_ccitt(data):04X};")
    lines.append("")

    lines.append("// ---- COBS ----")
    cobs_cases = [
        b"",
        b"\x00",
        b"\x11\x22\x00\x33",
        b"\x11\x00\x00\x00",
        b"hello world",
        bytes(range(1, 255)),  # 254 논제로 — 0xFF 블록 경계
        bytes(range(256)),
    ]
    lines.append(f"constexpr size_t COBS_CASE_COUNT = {len(cobs_cases)};")
    for i, raw in enumerate(cobs_cases):
        emit_bytes(lines, f"COBS_RAW_{i}", raw)
        emit_bytes(lines, f"COBS_ENC_{i}", cobs_encode(raw))
    lines.append("")

    lines.append("// ---- 논리 패킷 encode (헤더 7B + PAYLOAD + CRC16 LE) ----")
    packets = [
        ("PING", Packet(src=0x00, dst=0x01, type=MsgType.PING, seq=7)),
        ("SET_TEMPLATE", Packet(src=0x00, dst=0x02, type=MsgType.SET_TEMPLATE, seq=3,
                                payload=b"\x01")),
        ("SET_FIELD_KO", Packet(src=0x00, dst=0x01, type=MsgType.SET_FIELD, seq=42,
                                payload=build_set_field(2, "부스"))),
        ("SET_QR", Packet(src=0x00, dst=0x01, type=MsgType.SET_QR, seq=8,
                          payload=build_set_qr("https://x.io/a"))),
        ("COMMIT_BCAST", Packet(src=0x00, dst=0xFF, type=MsgType.COMMIT, seq=0xFF,
                                payload=b"\x01")),
        ("ACK_BUSY", Packet(src=0x01, dst=0x00, type=MsgType.ACK, seq=9,
                            payload=build_ack(9, AckResult.BUSY))),
        ("PONG", Packet(src=0x01, dst=0x00, type=MsgType.PONG, seq=5,
                        payload=build_pong(3900, -60, 0))),
        ("STATUS_RES", Packet(src=0x02, dst=0x00, type=MsgType.STATUS_RES, seq=6,
                              payload=build_status_res(3700, 5, 600, 1))),
        ("MAX_PAYLOAD", Packet(src=0x00, dst=0x01, type=MsgType.SET_FIELD, seq=1,
                               payload=bytes(range(200)))),
    ]
    lines.append(f"constexpr size_t PKT_CASE_COUNT = {len(packets)};")
    for i, (name, pkt) in enumerate(packets):
        lines.append(f"// [{i}] {name}")
        lines.append(f"constexpr uint8_t PKT_SRC_{i}  = 0x{pkt.src:02X};")
        lines.append(f"constexpr uint8_t PKT_DST_{i}  = 0x{pkt.dst:02X};")
        lines.append(f"constexpr uint8_t PKT_TYPE_{i} = 0x{int(pkt.type):02X};")
        lines.append(f"constexpr uint8_t PKT_SEQ_{i}  = 0x{pkt.seq:02X};")
        emit_bytes(lines, f"PKT_PAYLOAD_{i}", pkt.payload)
        emit_bytes(lines, f"PKT_WIRE_{i}", encode(pkt))
        emit_bytes(lines, f"PKT_FRAME_{i}", encode_frame(encode(pkt)))
    lines.append("")

    lines.append("// ---- 페이로드 빌더 (little-endian 확인용) ----")
    emit_bytes(lines, "PAYLOAD_SET_FIELD_KO", build_set_field(2, "부스"))
    emit_bytes(lines, "PAYLOAD_SET_QR", build_set_qr("https://x.io/a"))
    emit_bytes(lines, "PAYLOAD_ACK_BUSY", build_ack(9, AckResult.BUSY))
    emit_bytes(lines, "PAYLOAD_PONG", build_pong(3900, -60, 0))
    emit_bytes(lines, "PAYLOAD_STATUS_RES", build_status_res(3700, 5, 600, 1))
    lines.append("")

    lines.append("}  // namespace golden")
    lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(lines)} lines)")


if __name__ == "__main__":
    main()
