# E-FairBoard 백엔드(FastAPI + 가상 노드 시뮬레이터) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LoRa·e-Paper 하드웨어 없이 동작하는 E-FairBoard 중앙 관리 서버 — PROTOCOL.md v0.1 프로토콜 계층 + 가상 노드 시뮬레이터 + 게시물/배포/예약/통계 REST API.

**Architecture:** FastAPI 단일 프로세스. `protocol/`(패킷 codec·CRC16·COBS·stop-and-wait 링크)이 `transport/` 추상(바이트 스트림) 위에서 동작하고, 가상 모드에서는 lifespan이 `simulator/`(가상 게이트웨이·채널·노드 2개)를 asyncio 태스크로 함께 띄운다. 상태는 메모리(Pydantic) + JSON 스냅샷, DB 없음.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2 + pydantic-settings, APScheduler(인메모리), pytest + pytest-asyncio, httpx(TestClient), pyserial(실모드 전용 — 이 계획에서는 어댑터 자리만).

## Global Constraints

- 스펙: `docs/web/2026-07-08-web-design.md` (§ 번호는 이 문서 기준). 프로토콜 규격: `docs/PROTOCOL.md` v0.1
- 모든 경로는 저장소 루트 기준. 백엔드 루트 = `server/backend/`, 테스트 실행은 항상 `server/backend/`에서 `python -m pytest`
- 커밋은 **`wj` 브랜치에만** (CLAUDE.md 협업 헌법: main 직접 push 금지, force push 금지)
- 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 트레일러 추가
- 멀티바이트 정수는 전부 **little-endian** (스펙 §5.1)
- 패킷: 헤더 7B(VER·SRC·DST·TYPE·SEQ·FRAG·LEN) + PAYLOAD(≤200B) + CRC16(2B, LE). ⚠️ PROTOCOL.md §2 본문의 "8B 헤더" 문구는 필드 표(7필드×1B)와 불일치 — **필드 표를 정본으로 구현**하고, PROTOCOL.md 정정은 프로토콜 담당(우진)의 별도 작업
- SEQ 롤오버: `(seq + 1) & 0xFF`. CRC16: CCITT-FALSE(poly 0x1021, init 0xFFFF, no reflect)
- 타이밍 상수는 전부 `Settings`로 주입 가능해야 함 — 테스트는 축소값(airtime 0.01s 등), 운영 기본값은 스펙값(T_ack=1.5s, 재시도 3회, airtime 0.35s)
- 모든 신규 코드에 타입 힌트. 주석은 코드로 표현 못 하는 제약만
- Python 표준 라이브러리 + requirements.txt에 명시된 패키지만 사용

---

### Task 1: 백엔드 스캐폴드 + 설정

**Files:**
- Create: `server/backend/requirements.txt`
- Create: `server/backend/.env.example`
- Create: `server/backend/app/__init__.py` (빈 파일)
- Create: `server/backend/app/config.py`
- Create: `server/backend/tests/__init__.py` (빈 파일)
- Create: `server/backend/tests/test_config.py`
- Create: `server/backend/pytest.ini`

**Interfaces:**
- Produces: `app.config.Settings` (pydantic-settings) — 필드: `transport_mode: Literal["virtual","serial"]="virtual"`, `serial_port: str="COM3"`, `admin_password: str="changeme"`, `ack_timeout_s: float=1.5`, `link_retries: int=3`, `sim_airtime_s: float=0.35`, `sim_loss_rate: float=0.0`, `sim_refresh_partial_s: float=1.0`, `sim_refresh_full_s: float=3.0`, `status_poll_interval_s: float=15.0`, `data_file: str="data/state.json"`
- Produces: `app.config.get_settings() -> Settings` (lru_cache 싱글턴)

- [ ] **Step 1: 가상환경·의존성 파일 작성**

`server/backend/requirements.txt`:
```
fastapi==0.115.*
uvicorn[standard]==0.30.*
pydantic==2.*
pydantic-settings==2.*
apscheduler==3.10.*
httpx==0.27.*
pyserial==3.5
pytest==8.*
pytest-asyncio==0.24.*
```

`server/backend/.env.example`:
```
TRANSPORT_MODE=virtual
SERIAL_PORT=COM3
ADMIN_PASSWORD=changeme
```

`server/backend/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

설치 (저장소 루트에서, Windows PowerShell):
```powershell
cd server/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

- [ ] **Step 2: 실패하는 테스트 작성** — `server/backend/tests/test_config.py`

```python
from app.config import Settings, get_settings


def test_defaults_are_virtual_mode():
    s = Settings(_env_file=None)
    assert s.transport_mode == "virtual"
    assert s.ack_timeout_s == 1.5
    assert s.link_retries == 3


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
```

- [ ] **Step 3: 실패 확인**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'` 또는 ImportError

- [ ] **Step 4: 구현** — `server/backend/app/config.py`

```python
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    transport_mode: Literal["virtual", "serial"] = "virtual"
    serial_port: str = "COM3"
    admin_password: str = "changeme"

    # 링크 (PROTOCOL.md §5)
    ack_timeout_s: float = 1.5
    link_retries: int = 3

    # 시뮬레이터
    sim_airtime_s: float = 0.35
    sim_loss_rate: float = 0.0
    sim_refresh_partial_s: float = 1.0
    sim_refresh_full_s: float = 3.0

    # 모니터링·저장
    status_poll_interval_s: float = 15.0
    data_file: str = "data/state.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`server/backend/app/__init__.py`, `server/backend/tests/__init__.py`: 빈 파일 생성.

- [ ] **Step 5: 통과 확인**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: 커밋**

```bash
git add server/backend
git commit -m "feat(backend): 스캐폴드·Settings 추가"
```

---

### Task 2: CRC-16/CCITT-FALSE

**Files:**
- Create: `server/backend/app/protocol/__init__.py` (빈 파일)
- Create: `server/backend/app/protocol/crc16.py`
- Test: `server/backend/tests/test_crc16.py`

**Interfaces:**
- Produces: `app.protocol.crc16.crc16_ccitt(data: bytes) -> int` — CCITT-FALSE(poly 0x1021, init 0xFFFF, no reflect, xorout 0). 반환값 0~0xFFFF

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_crc16.py`

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_crc16.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현** — `server/backend/app/protocol/crc16.py`

```python
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
```

`server/backend/app/protocol/__init__.py`: 빈 파일.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_crc16.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app/protocol server/backend/tests/test_crc16.py
git commit -m "feat(protocol): CRC-16/CCITT-FALSE 구현"
```

---

### Task 3: COBS 인코딩/디코딩

**Files:**
- Create: `server/backend/app/protocol/cobs.py`
- Test: `server/backend/tests/test_cobs.py`

**Interfaces:**
- Produces: `cobs_encode(data: bytes) -> bytes` (결과에 0x00 없음), `cobs_decode(data: bytes) -> bytes`, `class CobsError(Exception)`
- 참고: 논리 패킷 최대 209B(7+200+2) < 254B라 0xFF 블록 분할은 실전에서 미발생 — 그래도 표준 알고리즘으로 구현

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_cobs.py`

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_cobs.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현** — `server/backend/app/protocol/cobs.py`

```python
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
        out += block
        i += code
        if code != 0xFF and i < len(data):
            out.append(0)
    return bytes(out)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_cobs.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app/protocol/cobs.py server/backend/tests/test_cobs.py
git commit -m "feat(protocol): COBS 인코딩/디코딩 구현"
```

---

### Task 4: 논리 패킷 codec + 페이로드 빌더/파서

**Files:**
- Create: `server/backend/app/protocol/packet.py`
- Test: `server/backend/tests/test_packet.py`

**Interfaces:**
- Produces:
  - 상수 `VER=0x01`, `GATEWAY_ID=0x00`, `BROADCAST=0xFF`, `FRAG_SINGLE=0x80`, `MAX_PAYLOAD=200`
  - `class MsgType(IntEnum)`: `PING=0x01, PONG=0x02, SET_TEMPLATE=0x10, SET_FIELD=0x11, SET_QR=0x12, COMMIT=0x13, IMG_FRAG=0x14, ACK=0x20, STATUS_REQ=0x30, STATUS_RES=0x31`
  - `class AckResult(IntEnum)`: `OK=0, CRC_FAIL=1, BUSY=2, BAD_TYPE=3`
  - `@dataclass(frozen=True) Packet(src:int, dst:int, type:MsgType, seq:int, payload:bytes=b"", frag:int=FRAG_SINGLE, ver:int=VER)`
  - `encode(p: Packet) -> bytes` / `decode(buf: bytes) -> Packet` / 예외 `PacketError`, `CrcError(PacketError)`
  - 빌더: `build_set_field(field_id:int, text:str) -> bytes`, `build_set_qr(url:str) -> bytes`, `build_pong(batt_mv:int, rssi:int, status:int) -> bytes`, `build_ack(ack_seq:int, result:AckResult) -> bytes`, `build_status_res(batt_mv:int, last_seq:int, uptime_s:int, err_cnt:int) -> bytes`
  - 파서: `parse_ack(payload) -> tuple[int, AckResult]`, `parse_pong(payload) -> tuple[int,int,int]` (batt_mv, rssi, status), `parse_status_res(payload) -> tuple[int,int,int,int]` (batt_mv, last_seq, uptime_s, err_cnt)

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_packet.py`

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_packet.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현** — `server/backend/app/protocol/packet.py`

```python
from dataclasses import dataclass, field
from enum import IntEnum

from .crc16 import crc16_ccitt

VER = 0x01
GATEWAY_ID = 0x00
BROADCAST = 0xFF
FRAG_SINGLE = 0x80  # bit7=LAST, 인덱스 0
MAX_PAYLOAD = 200
_HEADER_LEN = 7
_CRC_LEN = 2


class MsgType(IntEnum):
    PING = 0x01
    PONG = 0x02
    SET_TEMPLATE = 0x10
    SET_FIELD = 0x11
    SET_QR = 0x12
    COMMIT = 0x13
    IMG_FRAG = 0x14
    ACK = 0x20
    STATUS_REQ = 0x30
    STATUS_RES = 0x31


class AckResult(IntEnum):
    OK = 0
    CRC_FAIL = 1
    BUSY = 2
    BAD_TYPE = 3


class PacketError(Exception):
    pass


class CrcError(PacketError):
    pass


@dataclass(frozen=True)
class Packet:
    src: int
    dst: int
    type: MsgType
    seq: int
    payload: bytes = field(default=b"")
    frag: int = FRAG_SINGLE
    ver: int = VER


def encode(p: Packet) -> bytes:
    if len(p.payload) > MAX_PAYLOAD:
        raise PacketError(f"payload {len(p.payload)}B > {MAX_PAYLOAD}B")
    body = bytes([p.ver, p.src, p.dst, p.type, p.seq, p.frag, len(p.payload)]) + p.payload
    return body + crc16_ccitt(body).to_bytes(_CRC_LEN, "little")


def decode(buf: bytes) -> Packet:
    if len(buf) < _HEADER_LEN + _CRC_LEN:
        raise PacketError("buffer too short")
    length = buf[6]
    if len(buf) != _HEADER_LEN + length + _CRC_LEN:
        raise PacketError("LEN mismatch")
    body, crc = buf[:-_CRC_LEN], int.from_bytes(buf[-_CRC_LEN:], "little")
    if crc16_ccitt(body) != crc:
        raise CrcError("CRC16 mismatch")
    try:
        msg_type = MsgType(buf[3])
    except ValueError as exc:
        raise PacketError(f"unknown TYPE 0x{buf[3]:02X}") from exc
    return Packet(src=buf[1], dst=buf[2], type=msg_type, seq=buf[4],
                  payload=bytes(buf[7:-_CRC_LEN]), frag=buf[5], ver=buf[0])


# ---- 페이로드 빌더/파서 (PROTOCOL.md §3) ----

def build_set_field(field_id: int, text: str) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) > MAX_PAYLOAD - 2:
        raise PacketError("field text too long")
    return bytes([field_id, len(raw)]) + raw


def build_set_qr(url: str, qr_slot: int = 0) -> bytes:
    raw = url.encode("utf-8")
    if len(raw) > MAX_PAYLOAD - 2:
        raise PacketError("qr url too long")
    return bytes([qr_slot, len(raw)]) + raw


def build_ack(ack_seq: int, result: AckResult) -> bytes:
    return bytes([ack_seq, result])


def parse_ack(payload: bytes) -> tuple[int, AckResult]:
    return payload[0], AckResult(payload[1])


def build_pong(batt_mv: int, rssi: int, status: int) -> bytes:
    return batt_mv.to_bytes(2, "little") + rssi.to_bytes(1, "little", signed=True) \
        + bytes([status])


def parse_pong(payload: bytes) -> tuple[int, int, int]:
    return (int.from_bytes(payload[0:2], "little"),
            int.from_bytes(payload[2:3], "little", signed=True), payload[3])


def build_status_res(batt_mv: int, last_seq: int, uptime_s: int, err_cnt: int) -> bytes:
    return (batt_mv.to_bytes(2, "little") + bytes([last_seq])
            + uptime_s.to_bytes(2, "little") + bytes([err_cnt]))


def parse_status_res(payload: bytes) -> tuple[int, int, int, int]:
    return (int.from_bytes(payload[0:2], "little"), payload[2],
            int.from_bytes(payload[3:5], "little"), payload[5])
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_packet.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app/protocol/packet.py server/backend/tests/test_packet.py
git commit -m "feat(protocol): 논리 패킷 codec·페이로드 빌더 구현"
```

---

### Task 5: 시리얼 프레이밍 (COBS + 0x00 구분)

**Files:**
- Create: `server/backend/app/protocol/framing.py`
- Test: `server/backend/tests/test_framing.py`

**Interfaces:**
- Produces: `encode_frame(packet_bytes: bytes) -> bytes` (= `cobs_encode(...) + b"\x00"`), `class FrameAccumulator` — `feed(chunk: bytes) -> list[bytes]` (완성된 프레임의 COBS 디코딩 결과들을 반환, 불완전 프레임은 내부 버퍼에 유지, 깨진 COBS 프레임은 폐기하고 계속)

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_framing.py`

```python
from app.protocol.framing import FrameAccumulator, encode_frame


def test_encode_frame_ends_with_zero_and_has_no_inner_zero():
    frame = encode_frame(b"\x01\x02\x00\x03")
    assert frame[-1] == 0
    assert 0 not in frame[:-1]


def test_feed_single_complete_frame():
    acc = FrameAccumulator()
    assert acc.feed(encode_frame(b"abc")) == [b"abc"]


def test_feed_split_across_chunks():
    acc = FrameAccumulator()
    frame = encode_frame(b"\x10\x00\x20")
    assert acc.feed(frame[:2]) == []
    assert acc.feed(frame[2:]) == [b"\x10\x00\x20"]


def test_feed_multiple_frames_in_one_chunk():
    acc = FrameAccumulator()
    chunk = encode_frame(b"one") + encode_frame(b"two")
    assert acc.feed(chunk) == [b"one", b"two"]


def test_corrupt_frame_is_dropped_and_stream_continues():
    acc = FrameAccumulator()
    bad = b"\x05\x11\x22\x00"  # 잘린 COBS 블록 + 구분자
    out = acc.feed(bad + encode_frame(b"ok"))
    assert out == [b"ok"]


def test_empty_frame_ignored():
    acc = FrameAccumulator()
    assert acc.feed(b"\x00\x00") == []
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_framing.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현** — `server/backend/app/protocol/framing.py`

```python
from .cobs import CobsError, cobs_decode, cobs_encode


def encode_frame(packet_bytes: bytes) -> bytes:
    return cobs_encode(packet_bytes) + b"\x00"


class FrameAccumulator:
    """바이트 스트림에서 0x00 구분 COBS 프레임을 분리한다 (PROTOCOL.md §7)."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        self._buf += chunk
        frames: list[bytes] = []
        while (sep := self._buf.find(0)) != -1:
            raw = bytes(self._buf[:sep])
            del self._buf[: sep + 1]
            if not raw:
                continue
            try:
                frames.append(cobs_decode(raw))
            except CobsError:
                continue  # 깨진 프레임 폐기 — 상위 CRC가 최종 방어선
        return frames
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_framing.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app/protocol/framing.py server/backend/tests/test_framing.py
git commit -m "feat(protocol): COBS 프레임 어큐뮬레이터 구현"
```

---

### Task 6: Transport 추상 + VirtualTransport

**Files:**
- Create: `server/backend/app/transport/__init__.py` (빈 파일)
- Create: `server/backend/app/transport/base.py`
- Create: `server/backend/app/transport/virtual.py`
- Test: `server/backend/tests/test_transport_virtual.py`

**Interfaces:**
- Produces: `app.transport.base.Transport(ABC)` — `async def write(self, data: bytes) -> None`, `async def read(self) -> bytes` (1개 이상 바이트 청크 반환, 스트림 경계 보장 없음), `async def close(self) -> None` (기본 no-op)
- Produces: `app.transport.virtual.virtual_pair() -> tuple[Transport, Transport]` — 인메모리 duplex 페어: 한쪽 `write`가 다른 쪽 `read`로 나옴. 한쪽=서버(LinkManager), 반대쪽=가상 게이트웨이(Task 10)

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_transport_virtual.py`

```python
import asyncio

from app.transport.virtual import virtual_pair


async def test_write_on_a_is_read_on_b():
    a, b = virtual_pair()
    await a.write(b"\x01\x02")
    assert await b.read() == b"\x01\x02"


async def test_duplex_both_directions():
    a, b = virtual_pair()
    await a.write(b"ping")
    await b.write(b"pong")
    assert await b.read() == b"ping"
    assert await a.read() == b"pong"


async def test_read_waits_until_data(event_loop=None):
    a, b = virtual_pair()

    async def delayed_write():
        await asyncio.sleep(0.01)
        await a.write(b"x")

    task = asyncio.create_task(delayed_write())
    assert await asyncio.wait_for(b.read(), timeout=1.0) == b"x"
    await task
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_transport_virtual.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현**

`server/backend/app/transport/base.py`:
```python
from abc import ABC, abstractmethod


class Transport(ABC):
    """바이트 스트림 추상 — 상위(link)는 가상/시리얼을 구분하지 않는다 (스펙 §3)."""

    @abstractmethod
    async def write(self, data: bytes) -> None: ...

    @abstractmethod
    async def read(self) -> bytes: ...

    async def close(self) -> None:
        return None
```

`server/backend/app/transport/virtual.py`:
```python
import asyncio

from .base import Transport


class VirtualTransport(Transport):
    def __init__(self, rx: asyncio.Queue, tx: asyncio.Queue) -> None:
        self._rx = rx
        self._tx = tx

    async def write(self, data: bytes) -> None:
        await self._tx.put(bytes(data))

    async def read(self) -> bytes:
        return await self._rx.get()


def virtual_pair() -> tuple[VirtualTransport, VirtualTransport]:
    q_ab: asyncio.Queue = asyncio.Queue()
    q_ba: asyncio.Queue = asyncio.Queue()
    return VirtualTransport(q_ba, q_ab), VirtualTransport(q_ab, q_ba)
```

`server/backend/app/transport/__init__.py`: 빈 파일.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_transport_virtual.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app/transport server/backend/tests/test_transport_virtual.py
git commit -m "feat(transport): Transport 추상·인메모리 가상 페어 구현"
```

---

### Task 7: LinkManager — stop-and-wait 신뢰 전송

**Files:**
- Create: `server/backend/app/protocol/link.py`
- Test: `server/backend/tests/test_link.py`

**Interfaces:**
- Consumes: `Transport`(Task 6), `encode_frame/FrameAccumulator`(Task 5), `Packet/encode/decode/MsgType/AckResult/parse_ack`(Task 4)
- Produces: `app.protocol.link.LinkManager`
  - `__init__(self, transport: Transport, *, ack_timeout_s: float = 1.5, retries: int = 3, src: int = GATEWAY_ID)`
  - `async def start(self) -> None` / `async def stop(self) -> None` — 백그라운드 리더 태스크 기동/종료
  - `async def request(self, dst: int, type_: MsgType, payload: bytes = b"", *, expect: MsgType) -> Packet` — SEQ 발급→프레임 전송→응답 대기. `expect=MsgType.ACK`이면 `ack_seq`가 보낸 SEQ와 같고 `result==OK`인 ACK만 성공. `CRC_FAIL`·`BUSY`면 동일 SEQ 재전송(BUSY는 0.3s 대기 후), `BAD_TYPE`이면 즉시 `LinkProtocolError`. 그 외 `expect`(PONG/STATUS_RES)는 `src==dst`인 해당 타입 패킷이면 성공. 총 시도 = 1 + retries, 소진 시 `LinkTimeoutError`
  - 예외: `class LinkError(Exception)`, `class LinkTimeoutError(LinkError)`, `class LinkProtocolError(LinkError)`
  - 내부: `_next_seq()` — `(seq+1) & 0xFF` 롤오버. 동시 `request` 호출은 `asyncio.Lock`으로 직렬화(stop-and-wait 보장)

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_link.py`

테스트 헬퍼: transport 반대쪽 끝에서 "노드 대역"을 즉석 구현해 시나리오를 주입한다.

```python
import asyncio

import pytest

from app.protocol.framing import FrameAccumulator, encode_frame
from app.protocol.link import LinkManager, LinkProtocolError, LinkTimeoutError
from app.protocol.packet import (
    AckResult, MsgType, Packet, build_ack, build_pong, decode, encode,
)
from app.transport.virtual import virtual_pair


class FakePeer:
    """transport 반대쪽 끝 — 수신 패킷마다 스크립트된 응답을 보낸다."""

    def __init__(self, transport):
        self.transport = transport
        self.acc = FrameAccumulator()
        self.received: list[Packet] = []
        self.script = []  # 수신 순서대로 소비: "ok"|"drop"|"busy"|"bad_type"|"pong"
        self._task = None

    def start(self):
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            chunk = await self.transport.read()
            for raw in self.acc.feed(chunk):
                pkt = decode(raw)
                self.received.append(pkt)
                action = self.script.pop(0) if self.script else "ok"
                await self._respond(pkt, action)

    async def _respond(self, pkt: Packet, action: str):
        if action == "drop":
            return
        if action == "pong":
            reply = Packet(src=pkt.dst, dst=pkt.src, type=MsgType.PONG, seq=pkt.seq,
                           payload=build_pong(3900, -60, 0))
        else:
            result = {"ok": AckResult.OK, "busy": AckResult.BUSY,
                      "bad_type": AckResult.BAD_TYPE}[action]
            reply = Packet(src=pkt.dst, dst=pkt.src, type=MsgType.ACK, seq=pkt.seq,
                           payload=build_ack(pkt.seq, result))
        await self.transport.write(encode_frame(encode(reply)))

    def stop(self):
        if self._task:
            self._task.cancel()


@pytest.fixture
async def link_and_peer():
    server_side, peer_side = virtual_pair()
    link = LinkManager(server_side, ack_timeout_s=0.05, retries=3)
    await link.start()
    peer = FakePeer(peer_side)
    peer.start()
    yield link, peer
    peer.stop()
    await link.stop()


async def test_request_ok_first_try(link_and_peer):
    link, peer = link_and_peer
    ack = await link.request(0x01, MsgType.SET_TEMPLATE, b"\x00", expect=MsgType.ACK)
    assert ack.type == MsgType.ACK
    assert len(peer.received) == 1


async def test_retry_after_drop_then_success(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["drop", "ok"]
    await link.request(0x01, MsgType.COMMIT, b"\x00", expect=MsgType.ACK)
    assert len(peer.received) == 2
    # 재전송은 동일 SEQ (멱등 재적용 방지의 전제)
    assert peer.received[0].seq == peer.received[1].seq


async def test_all_retries_exhausted_raises_timeout(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["drop", "drop", "drop", "drop"]
    with pytest.raises(LinkTimeoutError):
        await link.request(0x01, MsgType.PING, expect=MsgType.PONG)
    assert len(peer.received) == 4  # 1 + retries(3)


async def test_busy_ack_triggers_retry(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["busy", "ok"]
    await link.request(0x01, MsgType.COMMIT, b"\x01", expect=MsgType.ACK)
    assert len(peer.received) == 2


async def test_bad_type_raises_immediately(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["bad_type"]
    with pytest.raises(LinkProtocolError):
        await link.request(0x01, MsgType.COMMIT, b"\x00", expect=MsgType.ACK)
    assert len(peer.received) == 1


async def test_ping_expects_pong(link_and_peer):
    link, peer = link_and_peer
    peer.script = ["pong"]
    pong = await link.request(0x01, MsgType.PING, expect=MsgType.PONG)
    assert pong.type == MsgType.PONG and pong.src == 0x01


async def test_seq_rollover():
    server_side, _ = virtual_pair()
    link = LinkManager(server_side)
    link._seq = 0xFF
    assert link._next_seq() == 0xFF
    assert link._next_seq() == 0x00
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_link.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현** — `server/backend/app/protocol/link.py`

```python
import asyncio

from ..transport.base import Transport
from .framing import FrameAccumulator, encode_frame
from .packet import (
    GATEWAY_ID, AckResult, MsgType, Packet, PacketError, decode, encode, parse_ack,
)

_BUSY_BACKOFF_S = 0.3


class LinkError(Exception):
    pass


class LinkTimeoutError(LinkError):
    pass


class LinkProtocolError(LinkError):
    pass


class LinkManager:
    """stop-and-wait 신뢰 전송 (PROTOCOL.md §5). 요청은 Lock으로 직렬화."""

    def __init__(self, transport: Transport, *, ack_timeout_s: float = 1.5,
                 retries: int = 3, src: int = GATEWAY_ID) -> None:
        self._transport = transport
        self._ack_timeout_s = ack_timeout_s
        self._retries = retries
        self._src = src
        self._seq = 0
        self._lock = asyncio.Lock()
        self._acc = FrameAccumulator()
        self._inbox: asyncio.Queue[Packet] = asyncio.Queue()
        self._reader: asyncio.Task | None = None

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq = (self._seq + 1) & 0xFF
        return seq

    async def start(self) -> None:
        self._reader = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
        await self._transport.close()

    async def _read_loop(self) -> None:
        while True:
            chunk = await self._transport.read()
            for raw in self._acc.feed(chunk):
                try:
                    self._inbox.put_nowait(decode(raw))
                except PacketError:
                    continue  # 깨진 패킷 폐기 — 송신측 타임아웃이 재전송

    def _drain_inbox(self) -> None:
        while not self._inbox.empty():
            self._inbox.get_nowait()

    async def request(self, dst: int, type_: MsgType, payload: bytes = b"", *,
                      expect: MsgType) -> Packet:
        async with self._lock:
            seq = self._next_seq()
            frame = encode_frame(encode(Packet(self._src, dst, type_, seq, payload)))
            attempts = 1 + self._retries
            for _ in range(attempts):
                self._drain_inbox()  # 이전 시도의 뒤늦은 응답 제거
                await self._transport.write(frame)
                try:
                    reply = await self._wait_reply(dst, seq, expect)
                except LinkTimeoutError:
                    continue
                if reply is not None:
                    return reply
                await asyncio.sleep(_BUSY_BACKOFF_S)  # BUSY → 대기 후 재전송
            raise LinkTimeoutError(
                f"no valid reply from 0x{dst:02X} after {attempts} attempts")

    async def _wait_reply(self, dst: int, seq: int, expect: MsgType) -> Packet | None:
        """성공 시 Packet, BUSY면 None(재시도 신호), 타임아웃이면 예외."""
        deadline = asyncio.get_running_loop().time() + self._ack_timeout_s
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise LinkTimeoutError("ack timeout")
            try:
                pkt = await asyncio.wait_for(self._inbox.get(), timeout=remaining)
            except TimeoutError:
                raise LinkTimeoutError("ack timeout") from None
            if pkt.src != dst:
                continue
            if expect == MsgType.ACK and pkt.type == MsgType.ACK:
                ack_seq, result = parse_ack(pkt.payload)
                if ack_seq != seq:
                    continue
                if result == AckResult.OK:
                    return pkt
                if result == AckResult.BAD_TYPE:
                    raise LinkProtocolError("node replied BAD_TYPE")
                return None  # CRC_FAIL·BUSY → 재시도
            if pkt.type == expect:
                return pkt
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_link.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 전체 테스트 회귀 확인 후 커밋**

Run: `python -m pytest -q`
Expected: 전부 PASS

```bash
git add server/backend/app/protocol/link.py server/backend/tests/test_link.py
git commit -m "feat(protocol): stop-and-wait LinkManager 구현 (재전송·SEQ 롤오버·BUSY 백오프)"
```

---

### Task 8: 템플릿 정의 (단일 소스)

**Files:**
- Create: `server/backend/app/protocol/templates.py`
- Test: `server/backend/tests/test_templates.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) FieldDef(id:int, name:str, x:int, y:int, font_size:int, max_bytes:int)`, `@dataclass(frozen=True) QrDef(x:int, y:int, size:int)`, `@dataclass(frozen=True) TemplateDef(id:int, name:str, fields:tuple[FieldDef,...], qr:QrDef)`
- Produces: `TEMPLATES: dict[int, TemplateDef]` — PROTOCOL.md §8의 4종. 좌표는 296×128 캔버스 기준(프론트 미리보기·펌웨어 상수의 기준 소스)
- Produces: `def as_dict() -> list[dict]` — `GET /api/templates` 응답 형태(JSON 직렬화 가능)

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_templates.py`

```python
from app.protocol.templates import TEMPLATES, as_dict


def test_four_templates_defined():
    assert set(TEMPLATES.keys()) == {0, 1, 2, 3}


def test_field_ids_match_protocol_spec():
    # PROTOCOL.md §8: 행사 안내(0)=필드 4개, 부스 지도(1)=2, 모집 공고(2)=3, 일정표(3)=4
    assert [len(TEMPLATES[i].fields) for i in range(4)] == [4, 2, 3, 4]
    for tpl in TEMPLATES.values():
        assert [f.id for f in tpl.fields] == list(range(len(tpl.fields)))


def test_max_bytes_fits_set_field_payload():
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            assert 0 < f.max_bytes <= 198  # SET_FIELD text 한도 (200-2)


def test_geometry_inside_296x128():
    for tpl in TEMPLATES.values():
        for f in tpl.fields:
            assert 0 <= f.x < 296 and 0 <= f.y < 128
        assert tpl.qr.x + tpl.qr.size <= 296 and tpl.qr.y + tpl.qr.size <= 128


def test_as_dict_is_json_shape():
    data = as_dict()
    assert len(data) == 4
    assert data[0]["fields"][0]["name"]
    assert {"x", "y", "size"} <= set(data[0]["qr"].keys())
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_templates.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현** — `server/backend/app/protocol/templates.py`

```python
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FieldDef:
    id: int
    name: str
    x: int
    y: int
    font_size: int
    max_bytes: int  # UTF-8 바이트 기준 (SET_FIELD text ≤ 198B)


@dataclass(frozen=True)
class QrDef:
    x: int
    y: int
    size: int


@dataclass(frozen=True)
class TemplateDef:
    id: int
    name: str
    fields: tuple[FieldDef, ...]
    qr: QrDef


# 296×128 기준 좌표 — 프론트 미리보기와 노드 펌웨어 상수의 단일 기준 소스 (스펙 §5.1)
TEMPLATES: dict[int, TemplateDef] = {
    0: TemplateDef(0, "행사 안내", (
        FieldDef(0, "제목", 8, 8, 24, 60),
        FieldDef(1, "일시", 8, 48, 16, 45),
        FieldDef(2, "장소", 8, 72, 16, 45),
        FieldDef(3, "비고", 8, 100, 12, 60),
    ), QrDef(224, 32, 64)),
    1: TemplateDef(1, "부스 지도", (
        FieldDef(0, "구역명", 8, 12, 24, 45),
        FieldDef(1, "부스번호", 8, 60, 32, 24),
    ), QrDef(224, 32, 64)),
    2: TemplateDef(2, "모집 공고", (
        FieldDef(0, "제목", 8, 8, 24, 60),
        FieldDef(1, "마감", 8, 52, 16, 45),
        FieldDef(2, "대상", 8, 80, 16, 60),
    ), QrDef(224, 32, 64)),
    3: TemplateDef(3, "일정표", (
        FieldDef(0, "날짜", 8, 8, 20, 30),
        FieldDef(1, "세션1", 8, 44, 14, 66),
        FieldDef(2, "세션2", 8, 72, 14, 66),
        FieldDef(3, "세션3", 8, 100, 14, 66),
    ), QrDef(240, 8, 48)),
}


def as_dict() -> list[dict]:
    return [asdict(tpl) for tpl in TEMPLATES.values()]
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_templates.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app/protocol/templates.py server/backend/tests/test_templates.py
git commit -m "feat(protocol): 템플릿 4종 정의 (좌표·폰트·최대길이 단일 소스)"
```

---

### Task 9: 가상 채널 + 가상 노드 상태머신

**Files:**
- Create: `server/backend/app/simulator/__init__.py` (빈 파일)
- Create: `server/backend/app/simulator/channel.py`
- Create: `server/backend/app/simulator/node.py`
- Test: `server/backend/tests/test_virtual_node.py`

**Interfaces:**
- Consumes: `Packet/encode/decode/MsgType/AckResult/build_*/parse_*`(Task 4)
- Produces: `app.simulator.channel.VirtualChannel`
  - `__init__(self, *, airtime_s: float = 0.35, loss_rate: float = 0.0, seed: int = 1234)`
  - `attach(self, participant) -> None` — participant는 `node_id: int` 속성과 `async def on_air(self, pkt: Packet) -> None`을 가진 객체
  - `async def transmit(self, pkt: Packet) -> None` — airtime 지연 후, 손실 판정을 통과하면 `dst`가 자기 id거나 `0xFF`인 모든 참여자(송신자 제외)의 `on_air` 호출
  - 속성 `loss_rate: float`, `airtime_s: float` — 런타임 변경 가능(sim API용)
- Produces: `app.simulator.node.VirtualNode(node_id, channel, *, refresh_partial_s=1.0, refresh_full_s=3.0, batt_start_mv=4100, batt_drain_mv_per_min=2.0)`
  - `powered: bool = True` — False면 완전 무응답
  - `display_state -> dict` — `{"template_id": int|None, "fields": {str(field_id): str}, "qr_url": str|None, "last_commit_at": float|None}` (커밋된 상태만)
  - `batt_mv -> int` — 시작값에서 경과 시간에 비례해 감소 (`time.monotonic` 기준)
  - `async def on_air(self, pkt: Packet)` — 상태머신 (스펙 §5.2): SET_*→스테이징+ACK, COMMIT→갱신 지연 후 커밋+ACK, PING→PONG, STATUS_REQ→STATUS_RES, 멱등((TYPE,SEQ) 중복 시 재적용 없이 ACK 재전송), 브로드캐스트 COMMIT ACK는 `node_id×0.2s` 슬롯 지연(PROTOCOL.md §5), IMG_FRAG 등 미지원 타입→ACK(BAD_TYPE)
  - `err_cnt: int`, `uptime_s -> int`, `last_seq: int` — STATUS_RES 재료

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_virtual_node.py`

```python
import asyncio

import pytest

from app.protocol.packet import (
    GATEWAY_ID, AckResult, MsgType, Packet,
    build_set_field, build_set_qr, parse_ack, parse_pong, parse_status_res,
)
from app.simulator.channel import VirtualChannel
from app.simulator.node import VirtualNode


class GatewaySpy:
    """채널에 참여해 노드 응답을 수집하는 게이트웨이 대역."""

    node_id = GATEWAY_ID

    def __init__(self):
        self.inbox: asyncio.Queue[Packet] = asyncio.Queue()

    async def on_air(self, pkt: Packet):
        await self.inbox.put(pkt)

    async def send_and_wait(self, channel, pkt: Packet) -> Packet:
        await channel.transmit(pkt)
        return await asyncio.wait_for(self.inbox.get(), timeout=1.0)


@pytest.fixture
def rig():
    channel = VirtualChannel(airtime_s=0.0, loss_rate=0.0)
    node = VirtualNode(0x01, channel, refresh_partial_s=0.0, refresh_full_s=0.0)
    gw = GatewaySpy()
    channel.attach(node)
    channel.attach(gw)
    return channel, node, gw


async def test_set_field_stages_but_does_not_display(rig):
    channel, node, gw = rig
    ack = await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.SET_FIELD, 1, build_set_field(0, "제목")))
    assert parse_ack(ack.payload) == (1, AckResult.OK)
    assert node.display_state["fields"] == {}  # 커밋 전이므로 화면 없음


async def test_commit_applies_staged_state(rig):
    channel, node, gw = rig
    await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.SET_TEMPLATE, 1, b"\x02"))
    await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.SET_FIELD, 2, build_set_field(0, "모집")))
    await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.SET_QR, 3, build_set_qr("https://x.io")))
    await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.COMMIT, 4, b"\x00"))
    state = node.display_state
    assert state["template_id"] == 2
    assert state["fields"] == {"0": "모집"}
    assert state["qr_url"] == "https://x.io"
    assert state["last_commit_at"] is not None


async def test_duplicate_seq_is_idempotent(rig):
    channel, node, gw = rig
    pkt = Packet(GATEWAY_ID, 0x01, MsgType.SET_FIELD, 9, build_set_field(0, "A"))
    ack1 = await gw.send_and_wait(channel, pkt)
    ack2 = await gw.send_and_wait(channel, pkt)  # 동일 (TYPE,SEQ) 재전송
    assert parse_ack(ack1.payload) == parse_ack(ack2.payload) == (9, AckResult.OK)
    # 스테이징이 한 번만 적용됐는지는 커밋 후 값으로 확인
    await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.COMMIT, 10, b"\x00"))
    assert node.display_state["fields"]["0"] == "A"


async def test_ping_pong_reports_battery(rig):
    channel, node, gw = rig
    pong = await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.PING, 5))
    assert pong.type == MsgType.PONG
    batt, rssi, status = parse_pong(pong.payload)
    assert 3000 < batt <= 4200 and rssi < 0


async def test_status_res_fields(rig):
    channel, node, gw = rig
    await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.SET_TEMPLATE, 1, b"\x00"))
    res = await gw.send_and_wait(channel, Packet(GATEWAY_ID, 0x01, MsgType.STATUS_REQ, 2))
    batt, last_seq, uptime, err = parse_status_res(res.payload)
    assert res.type == MsgType.STATUS_RES and last_seq == 1 and err == 0


async def test_powered_off_node_is_silent(rig):
    channel, node, gw = rig
    node.powered = False
    await channel.transmit(Packet(GATEWAY_ID, 0x01, MsgType.PING, 6))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(gw.inbox.get(), timeout=0.05)


async def test_unsupported_type_acks_bad_type(rig):
    channel, node, gw = rig
    ack = await gw.send_and_wait(channel, Packet(
        GATEWAY_ID, 0x01, MsgType.IMG_FRAG, 7, b"\x00"))
    assert parse_ack(ack.payload) == (7, AckResult.BAD_TYPE)


async def test_channel_loss_drops_packet():
    channel = VirtualChannel(airtime_s=0.0, loss_rate=1.0)
    node = VirtualNode(0x01, channel, refresh_partial_s=0.0, refresh_full_s=0.0)
    gw = GatewaySpy()
    channel.attach(node)
    channel.attach(gw)
    await channel.transmit(Packet(GATEWAY_ID, 0x01, MsgType.PING, 1))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(gw.inbox.get(), timeout=0.05)


async def test_broadcast_reaches_all_nodes():
    channel = VirtualChannel(airtime_s=0.0, loss_rate=0.0)
    n1 = VirtualNode(0x01, channel, refresh_partial_s=0.0, refresh_full_s=0.0)
    n2 = VirtualNode(0x02, channel, refresh_partial_s=0.0, refresh_full_s=0.0)
    gw = GatewaySpy()
    for p in (n1, n2, gw):
        channel.attach(p)
    await channel.transmit(Packet(GATEWAY_ID, 0xFF, MsgType.SET_TEMPLATE, 1, b"\x01"))
    acks = [await asyncio.wait_for(gw.inbox.get(), timeout=1.0) for _ in range(2)]
    assert {a.src for a in acks} == {0x01, 0x02}
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_virtual_node.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현**

`server/backend/app/simulator/channel.py`:
```python
import asyncio
import random
from typing import Protocol

from ..protocol.packet import BROADCAST, Packet


class Participant(Protocol):
    node_id: int

    async def on_air(self, pkt: Packet) -> None: ...


class VirtualChannel:
    """가상 LoRa 매체 — airtime 지연과 확률적 손실을 주입한다 (스펙 §5.2)."""

    def __init__(self, *, airtime_s: float = 0.35, loss_rate: float = 0.0,
                 seed: int = 1234) -> None:
        self.airtime_s = airtime_s
        self.loss_rate = loss_rate
        self._rng = random.Random(seed)
        self._participants: list[Participant] = []

    def attach(self, participant: Participant) -> None:
        self._participants.append(participant)

    async def transmit(self, pkt: Packet) -> None:
        if self.airtime_s > 0:
            await asyncio.sleep(self.airtime_s)
        if self._rng.random() < self.loss_rate:
            return  # 패킷 손실
        for p in self._participants:
            if p.node_id == pkt.src:
                continue
            if pkt.dst == BROADCAST or pkt.dst == p.node_id:
                asyncio.create_task(p.on_air(pkt))
```

`server/backend/app/simulator/node.py`:
```python
import asyncio
import time

from ..protocol.packet import (
    BROADCAST, AckResult, MsgType, Packet,
    build_ack, build_pong, build_status_res,
)

_BROADCAST_ACK_SLOT_S = 0.2  # PROTOCOL.md §5: NodeID×200ms


class VirtualNode:
    """노드 펌웨어와 동일 동작의 상태머신 — 지시서의 스펙이 된다 (스펙 §5.2)."""

    def __init__(self, node_id: int, channel, *, refresh_partial_s: float = 1.0,
                 refresh_full_s: float = 3.0, batt_start_mv: int = 4100,
                 batt_drain_mv_per_min: float = 2.0) -> None:
        self.node_id = node_id
        self._channel = channel
        self._refresh_s = {0: refresh_partial_s, 1: refresh_full_s}
        self._batt_start_mv = batt_start_mv
        self.batt_drain_mv_per_min = batt_drain_mv_per_min
        self._boot_at = time.monotonic()
        self.powered = True
        self.err_cnt = 0
        self.last_seq = 0
        self._last_handled: tuple[int, int] | None = None  # (TYPE, SEQ) 멱등
        self._staged_template: int | None = None
        self._staged_fields: dict[int, str] = {}
        self._staged_qr: str | None = None
        self._template_id: int | None = None
        self._fields: dict[int, str] = {}
        self._qr_url: str | None = None
        self._last_commit_at: float | None = None

    @property
    def batt_mv(self) -> int:
        drained = (time.monotonic() - self._boot_at) / 60 * self.batt_drain_mv_per_min
        return max(3000, int(self._batt_start_mv - drained))

    @property
    def uptime_s(self) -> int:
        return int(time.monotonic() - self._boot_at) & 0xFFFF

    @property
    def display_state(self) -> dict:
        return {
            "template_id": self._template_id,
            "fields": {str(k): v for k, v in self._fields.items()},
            "qr_url": self._qr_url,
            "last_commit_at": self._last_commit_at,
        }

    async def on_air(self, pkt: Packet) -> None:
        if not self.powered:
            return
        if pkt.type in (MsgType.PING, MsgType.STATUS_REQ):
            await self._reply_query(pkt)
            return
        # 멱등: 직전과 동일 (TYPE,SEQ)면 재적용 없이 ACK만 재전송
        if self._last_handled == (pkt.type, pkt.seq):
            await self._ack(pkt, AckResult.OK)
            return
        result = self._apply(pkt)
        if result == AckResult.OK and pkt.type == MsgType.COMMIT:
            await asyncio.sleep(self._refresh_s.get(pkt.payload[0], 1.0))
            self._commit()
        if result == AckResult.OK:
            self._last_handled = (pkt.type, pkt.seq)
            self.last_seq = pkt.seq
        else:
            self.err_cnt += 1
        await self._ack(pkt, result)

    def _apply(self, pkt: Packet) -> AckResult:
        if pkt.type == MsgType.SET_TEMPLATE:
            self._staged_template = pkt.payload[0]
        elif pkt.type == MsgType.SET_FIELD:
            text_len = pkt.payload[1]
            self._staged_fields[pkt.payload[0]] = pkt.payload[2:2 + text_len].decode("utf-8")
        elif pkt.type == MsgType.SET_QR:
            url_len = pkt.payload[1]
            self._staged_qr = pkt.payload[2:2 + url_len].decode("utf-8")
        elif pkt.type == MsgType.COMMIT:
            pass  # 반영은 on_air에서 갱신 지연 후
        else:
            return AckResult.BAD_TYPE
        return AckResult.OK

    def _commit(self) -> None:
        if self._staged_template is not None:
            self._template_id = self._staged_template
        self._fields.update(self._staged_fields)
        if self._staged_qr is not None:
            self._qr_url = self._staged_qr
        self._staged_fields = {}
        self._staged_qr = None
        self._staged_template = None
        self._last_commit_at = time.time()

    async def _ack(self, pkt: Packet, result: AckResult) -> None:
        if pkt.dst == BROADCAST:
            await asyncio.sleep(self.node_id * _BROADCAST_ACK_SLOT_S)
        await self._channel.transmit(Packet(
            self.node_id, pkt.src, MsgType.ACK, pkt.seq,
            build_ack(pkt.seq, result)))

    async def _reply_query(self, pkt: Packet) -> None:
        if pkt.type == MsgType.PING:
            payload = build_pong(self.batt_mv, -60, 0)
            reply_type = MsgType.PONG
        else:
            payload = build_status_res(self.batt_mv, self.last_seq,
                                       self.uptime_s, self.err_cnt)
            reply_type = MsgType.STATUS_RES
        await self._channel.transmit(Packet(
            self.node_id, pkt.src, reply_type, pkt.seq, payload))
```

`server/backend/app/simulator/__init__.py`: 빈 파일.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_virtual_node.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app/simulator server/backend/tests/test_virtual_node.py
git commit -m "feat(sim): 가상 LoRa 채널·가상 노드 상태머신 구현"
```

---

### Task 10: 가상 게이트웨이 + 프로토콜 E2E (손실 주입 포함)

**Files:**
- Create: `server/backend/app/simulator/gateway.py`
- Create: `server/backend/app/simulator/rig.py`
- Test: `server/backend/tests/test_protocol_e2e.py`

**Interfaces:**
- Consumes: `virtual_pair`(Task 6), `FrameAccumulator/encode_frame`(Task 5), `VirtualChannel/VirtualNode`(Task 9), `LinkManager`(Task 7)
- Produces: `app.simulator.gateway.VirtualGateway(transport, channel)` — `node_id = GATEWAY_ID`. `async def start()/stop()`. 역할: transport에서 프레임 수신→decode→`channel.transmit`; `on_air`로 받은 노드 응답→encode_frame→transport로 송신 (실제 게이트웨이 펌웨어와 동일 역할)
- Produces: `app.simulator.rig.SimRig` — 전체 조립 헬퍼 (lifespan과 테스트가 공용):
  - `@classmethod def build(cls, settings: Settings) -> "SimRig"` — virtual_pair→서버측 `LinkManager`, 반대쪽 `VirtualGateway`+`VirtualChannel`+`VirtualNode(0x01)`, `VirtualNode(0x02)` 조립
  - 속성: `link: LinkManager`, `channel: VirtualChannel`, `nodes: dict[int, VirtualNode]`
  - `async def start()/stop()`

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_protocol_e2e.py`

```python
import pytest

from app.config import Settings
from app.protocol.link import LinkManager, LinkTimeoutError
from app.protocol.packet import MsgType, build_set_field, build_set_qr, parse_pong
from app.simulator.rig import SimRig


def fast_settings(**over) -> Settings:
    # link_retries=12: 양방향 손실 30% 스트레스 대비 (운영 기본은 3)
    return Settings(_env_file=None, sim_airtime_s=0.0, ack_timeout_s=0.05,
                    link_retries=12, sim_refresh_partial_s=0.0,
                    sim_refresh_full_s=0.0, **over)


@pytest.fixture
async def rig():
    r = SimRig.build(fast_settings())
    await r.start()
    yield r
    await r.stop()


async def deploy_sequence(link: LinkManager, node_id: int):
    await link.request(node_id, MsgType.SET_TEMPLATE, b"\x00", expect=MsgType.ACK)
    await link.request(node_id, MsgType.SET_FIELD,
                       build_set_field(0, "임베디드 경진대회"), expect=MsgType.ACK)
    await link.request(node_id, MsgType.SET_QR,
                       build_set_qr("https://4this.io/e"), expect=MsgType.ACK)
    await link.request(node_id, MsgType.COMMIT, b"\x00", expect=MsgType.ACK)


async def test_full_deploy_updates_node_display(rig):
    await deploy_sequence(rig.link, 0x01)
    state = rig.nodes[0x01].display_state
    assert state["template_id"] == 0
    assert state["fields"]["0"] == "임베디드 경진대회"
    assert state["qr_url"] == "https://4this.io/e"


async def test_deploy_succeeds_with_30pct_loss(rig):
    rig.channel.loss_rate = 0.3  # 스펙 §8: 손실 30%에서도 재전송으로 성공
    for _ in range(3):  # 여러 번 반복해도 안정적으로 성공해야 함
        await deploy_sequence(rig.link, 0x02)
    assert rig.nodes[0x02].display_state["template_id"] == 0


async def test_powered_off_node_times_out(rig):
    rig.nodes[0x01].powered = False
    with pytest.raises(LinkTimeoutError):
        await rig.link.request(0x01, MsgType.PING, expect=MsgType.PONG)


async def test_ping_returns_battery(rig):
    pong = await rig.link.request(0x02, MsgType.PING, expect=MsgType.PONG)
    batt, _, _ = parse_pong(pong.payload)
    assert batt > 3000
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_protocol_e2e.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현**

`server/backend/app/simulator/gateway.py`:
```python
import asyncio

from ..protocol.framing import FrameAccumulator, encode_frame
from ..protocol.packet import GATEWAY_ID, Packet, PacketError, decode, encode
from ..transport.base import Transport
from .channel import VirtualChannel


class VirtualGateway:
    """서버(시리얼 프레임) ↔ 가상 LoRa 채널 중계 — 게이트웨이 펌웨어와 동일 역할."""

    node_id = GATEWAY_ID

    def __init__(self, transport: Transport, channel: VirtualChannel) -> None:
        self._transport = transport
        self._channel = channel
        self._acc = FrameAccumulator()
        self._reader: asyncio.Task | None = None

    async def start(self) -> None:
        self._reader = asyncio.create_task(self._serial_loop())

    async def stop(self) -> None:
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass

    async def _serial_loop(self) -> None:
        while True:
            chunk = await self._transport.read()
            for raw in self._acc.feed(chunk):
                try:
                    pkt = decode(raw)
                except PacketError:
                    continue
                await self._channel.transmit(pkt)

    async def on_air(self, pkt: Packet) -> None:
        if pkt.dst != GATEWAY_ID:
            return
        await self._transport.write(encode_frame(encode(pkt)))
```

`server/backend/app/simulator/rig.py`:
```python
from ..config import Settings
from ..protocol.link import LinkManager
from ..transport.virtual import virtual_pair
from .channel import VirtualChannel
from .gateway import VirtualGateway
from .node import VirtualNode

NODE_IDS = (0x01, 0x02)


class SimRig:
    """가상 모드 전체 조립 — lifespan과 테스트가 공용 (스펙 §3)."""

    def __init__(self, link: LinkManager, gateway: VirtualGateway,
                 channel: VirtualChannel, nodes: dict[int, VirtualNode]) -> None:
        self.link = link
        self.gateway = gateway
        self.channel = channel
        self.nodes = nodes

    @classmethod
    def build(cls, settings: Settings) -> "SimRig":
        server_side, gateway_side = virtual_pair()
        link = LinkManager(server_side, ack_timeout_s=settings.ack_timeout_s,
                           retries=settings.link_retries)
        channel = VirtualChannel(airtime_s=settings.sim_airtime_s,
                                 loss_rate=settings.sim_loss_rate)
        gateway = VirtualGateway(gateway_side, channel)
        nodes = {
            nid: VirtualNode(nid, channel,
                             refresh_partial_s=settings.sim_refresh_partial_s,
                             refresh_full_s=settings.sim_refresh_full_s)
            for nid in NODE_IDS
        }
        channel.attach(gateway)
        for node in nodes.values():
            channel.attach(node)
        return cls(link, gateway, channel, nodes)

    async def start(self) -> None:
        await self.gateway.start()
        await self.link.start()

    async def stop(self) -> None:
        await self.link.stop()
        await self.gateway.stop()
```

- [ ] **Step 4: 통과 확인 (전체 회귀 포함)**

Run: `python -m pytest -q`
Expected: 전부 PASS — 특히 `test_deploy_succeeds_with_30pct_loss`가 재전송 경로를 검증

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app/simulator server/backend/tests/test_protocol_e2e.py
git commit -m "feat(sim): 가상 게이트웨이·SimRig 조립, 손실 30% E2E 통과"
```

---

### Task 11: 도메인 모델 + JSON 스냅샷 저장소

**Files:**
- Create: `server/backend/app/models.py`
- Create: `server/backend/app/store.py`
- Test: `server/backend/tests/test_store.py`

**Interfaces:**
- Produces (`app.models`, 전부 Pydantic BaseModel):
  - `Post(id:int, title:str, template_id:int, fields:dict[str,str], qr_url:str="", created_at:datetime, updated_at:datetime)`
  - `StatusSample(t:datetime, batt_mv:int, rssi:int)`
  - `NodeInfo(id:int, name:str, status:Literal["online","offline","unknown"]="unknown", batt_mv:int|None=None, rssi:int|None=None, last_seen_at:datetime|None=None, current_post_id:int|None=None, history:list[StatusSample]=[])` — history는 append 시 `HISTORY_MAX=2000` 초과분을 앞에서 잘라냄(store가 담당)
  - `DeployTarget(node_id:int, status:Literal["pending","sending","success","failed"]="pending", attempts:int=0, error:str="", acked_at:datetime|None=None)`
  - `Deployment(id:int, post_id:int, status:Literal["running","success","partial","failed"]="running", trigger:Literal["manual","scheduled"]="manual", refresh_mode:int=0, created_at:datetime, finished_at:datetime|None=None, targets:list[DeployTarget])`
  - `Schedule(id:int, post_id:int, node_ids:list[int], run_at:datetime, status:Literal["pending","done","cancelled"]="pending", created_at:datetime)`
  - `AppState(posts:dict[int,Post]={}, nodes:dict[int,NodeInfo]={}, deployments:dict[int,Deployment]={}, schedules:dict[int,Schedule]={}, next_post_id:int=1, next_deployment_id:int=1, next_schedule_id:int=1)`
- Produces (`app.store`):
  - `class Store` — `__init__(self, path: Path)`, `state: AppState`
  - `def load(self) -> None` — 파일 없으면 빈 AppState, 있으면 파싱(깨진 파일이면 `.bak`로 옮기고 빈 상태로 시작)
  - `def save(self) -> None` — `path.tmp`에 쓰고 `os.replace`로 원자 교체 (디렉토리 자동 생성)
  - `def next_id(self, counter: Literal["post","deployment","schedule"]) -> int`
  - `def add_history(self, node_id: int, sample: StatusSample) -> None` — 링버퍼(HISTORY_MAX=2000)
  - `def seed_nodes(self, node_ids: list[int]) -> None` — 없는 노드만 `NodeInfo(id, name=f"노드 {id}")`로 추가

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_store.py`

```python
from datetime import datetime, timezone

from app.models import AppState, NodeInfo, Post, StatusSample
from app.store import HISTORY_MAX, Store


def now():
    return datetime.now(timezone.utc)


def test_load_missing_file_gives_empty_state(tmp_path):
    store = Store(tmp_path / "state.json")
    store.load()
    assert store.state == AppState()


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "data" / "state.json"  # 하위 디렉토리 자동 생성 확인
    store = Store(path)
    store.load()
    pid = store.next_id("post")
    store.state.posts[pid] = Post(id=pid, title="행사", template_id=0,
                                  fields={"0": "제목"}, created_at=now(),
                                  updated_at=now())
    store.save()

    fresh = Store(path)
    fresh.load()
    assert fresh.state.posts[pid].title == "행사"
    assert fresh.state.next_post_id == 2


def test_corrupt_file_is_backed_up_and_reset(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ not json !", encoding="utf-8")
    store = Store(path)
    store.load()
    assert store.state == AppState()
    assert path.with_suffix(".json.bak").exists()


def test_next_id_increments_per_counter(tmp_path):
    store = Store(tmp_path / "s.json")
    store.load()
    assert store.next_id("post") == 1
    assert store.next_id("post") == 2
    assert store.next_id("deployment") == 1


def test_history_ring_buffer_capped(tmp_path):
    store = Store(tmp_path / "s.json")
    store.load()
    store.seed_nodes([1])
    for i in range(HISTORY_MAX + 10):
        store.add_history(1, StatusSample(t=now(), batt_mv=4000 - i, rssi=-60))
    hist = store.state.nodes[1].history
    assert len(hist) == HISTORY_MAX
    assert hist[-1].batt_mv == 4000 - (HISTORY_MAX + 9)  # 최신이 마지막


def test_seed_nodes_does_not_overwrite_existing(tmp_path):
    store = Store(tmp_path / "s.json")
    store.load()
    store.state.nodes[1] = NodeInfo(id=1, name="1층 로비")
    store.seed_nodes([1, 2])
    assert store.state.nodes[1].name == "1층 로비"
    assert store.state.nodes[2].name == "노드 2"
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_store.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현**

`server/backend/app/models.py`:
```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Post(BaseModel):
    id: int
    title: str
    template_id: int
    fields: dict[str, str] = Field(default_factory=dict)  # field_id(str) -> text
    qr_url: str = ""
    created_at: datetime
    updated_at: datetime


class StatusSample(BaseModel):
    t: datetime
    batt_mv: int
    rssi: int


class NodeInfo(BaseModel):
    id: int
    name: str
    status: Literal["online", "offline", "unknown"] = "unknown"
    batt_mv: int | None = None
    rssi: int | None = None
    last_seen_at: datetime | None = None
    current_post_id: int | None = None
    history: list[StatusSample] = Field(default_factory=list)


class DeployTarget(BaseModel):
    node_id: int
    status: Literal["pending", "sending", "success", "failed"] = "pending"
    attempts: int = 0
    error: str = ""
    acked_at: datetime | None = None


class Deployment(BaseModel):
    id: int
    post_id: int
    status: Literal["running", "success", "partial", "failed"] = "running"
    trigger: Literal["manual", "scheduled"] = "manual"
    refresh_mode: int = 0  # 0=부분, 1=전체
    created_at: datetime
    finished_at: datetime | None = None
    targets: list[DeployTarget] = Field(default_factory=list)


class Schedule(BaseModel):
    id: int
    post_id: int
    node_ids: list[int]
    run_at: datetime
    status: Literal["pending", "done", "cancelled"] = "pending"
    created_at: datetime


class AppState(BaseModel):
    posts: dict[int, Post] = Field(default_factory=dict)
    nodes: dict[int, NodeInfo] = Field(default_factory=dict)
    deployments: dict[int, Deployment] = Field(default_factory=dict)
    schedules: dict[int, Schedule] = Field(default_factory=dict)
    next_post_id: int = 1
    next_deployment_id: int = 1
    next_schedule_id: int = 1
```

`server/backend/app/store.py`:
```python
import os
from pathlib import Path
from typing import Literal

from .models import AppState, NodeInfo, StatusSample

HISTORY_MAX = 2000  # 노드당 이력 링버퍼 한도 (스펙 §5.3)


class Store:
    """메모리 상태 + JSON 원자적 스냅샷 (스펙 §5.3). DB 없음."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self.state = AppState()

    def load(self) -> None:
        if not self._path.exists():
            self.state = AppState()
            return
        try:
            self.state = AppState.model_validate_json(
                self._path.read_text(encoding="utf-8"))
        except ValueError:
            backup = self._path.with_suffix(self._path.suffix + ".bak")
            os.replace(self._path, backup)
            self.state = AppState()

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(self.state.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def next_id(self, counter: Literal["post", "deployment", "schedule"]) -> int:
        attr = f"next_{counter}_id"
        value = getattr(self.state, attr)
        setattr(self.state, attr, value + 1)
        return value

    def add_history(self, node_id: int, sample: StatusSample) -> None:
        history = self.state.nodes[node_id].history
        history.append(sample)
        if len(history) > HISTORY_MAX:
            del history[: len(history) - HISTORY_MAX]

    def seed_nodes(self, node_ids: list[int]) -> None:
        for nid in node_ids:
            if nid not in self.state.nodes:
                self.state.nodes[nid] = NodeInfo(id=nid, name=f"노드 {nid}")
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_store.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app/models.py server/backend/app/store.py server/backend/tests/test_store.py
git commit -m "feat(store): Pydantic 도메인 모델·JSON 원자 스냅샷 저장소 구현"
```

---

### Task 12: 인증 + FastAPI 앱 뼈대

**Files:**
- Create: `server/backend/app/auth.py`
- Create: `server/backend/app/deps.py`
- Create: `server/backend/app/routers/__init__.py` (빈 파일)
- Create: `server/backend/app/routers/auth.py`
- Create: `server/backend/app/main.py`
- Create: `server/backend/tests/conftest.py`
- Test: `server/backend/tests/test_auth.py`

**Interfaces:**
- Produces (`app.auth`): `class TokenRegistry` — `issue() -> str`(secrets.token_urlsafe(32), 내부 set 보관), `is_valid(token: str) -> bool`
- Produces (`app.deps`): 앱 전역 의존성 접근자 — `get_store(request) -> Store`, `get_rig(request) -> SimRig | None`, `get_tokens(request) -> TokenRegistry`, `require_token(...)`(FastAPI Depends — `Authorization: Bearer <t>` 검증, 실패 시 401). 전부 `request.app.state.*`에서 꺼낸다
- Produces (`app.main`): `def create_app(settings: Settings | None = None) -> FastAPI`
  - lifespan: `Store` 로드+`seed_nodes([0x01, 0x02])`(virtual 모드), `TokenRegistry` 생성, virtual 모드면 `SimRig.build(settings)`+`start()`, 종료 시 `stop()`+`store.save()`. 전부 `app.state.store/rig/tokens/settings`에 보관
  - `/api/auth` 라우터 등록. (다른 라우터는 후속 태스크에서 이 파일에 한 줄씩 추가)
- Produces (`app.routers.auth`): `POST /api/auth/login` — body `{"password": str}` → 200 `{"token": str}` / 401
- Produces (테스트 픽스처 `tests/conftest.py`): `client` — 축소 타이밍 Settings로 `create_app`을 만들고 `TestClient`를 `with`로 감싸(lifespan 실행) 반환. `auth_headers(client) -> dict` — 로그인 후 `{"Authorization": "Bearer ..."}`

- [ ] **Step 1: 실패하는 테스트 작성**

`server/backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_PASSWORD = "test-pass"


def make_settings(tmp_path, **over) -> Settings:
    # link_retries=12: 손실 30% 테스트는 명령·ACK 양방향 손실이라 시도당
    # 성공률이 0.49로 떨어짐 → 재시도 여유 필요. 운영 기본은 스펙값 3.
    return Settings(_env_file=None, admin_password=TEST_PASSWORD,
                    transport_mode="virtual", sim_airtime_s=0.0,
                    ack_timeout_s=0.05, link_retries=12,
                    sim_refresh_partial_s=0.0, sim_refresh_full_s=0.0,
                    status_poll_interval_s=3600.0,
                    data_file=str(tmp_path / "state.json"), **over)


@pytest.fixture
def client(tmp_path):
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    token = client.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}
```

`server/backend/tests/test_auth.py`:
```python
from tests.conftest import TEST_PASSWORD


def test_login_with_correct_password_returns_token(client):
    res = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert res.status_code == 200
    assert len(res.json()["token"]) > 20


def test_login_with_wrong_password_401(client):
    assert client.post("/api/auth/login",
                       json={"password": "nope"}).status_code == 401
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_auth.py -v`
Expected: FAIL — ModuleNotFoundError (app.main 없음)

- [ ] **Step 3: 구현**

`server/backend/app/auth.py`:
```python
import secrets


class TokenRegistry:
    """서버 메모리 토큰 — 재시작 시 전부 무효(재로그인, 스펙 §5.4)."""

    def __init__(self) -> None:
        self._tokens: set[str] = set()

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens.add(token)
        return token

    def is_valid(self, token: str) -> bool:
        return token in self._tokens
```

`server/backend/app/deps.py`:
```python
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import TokenRegistry
from .store import Store

_bearer = HTTPBearer(auto_error=False)


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_rig(request: Request):
    return getattr(request.app.state, "rig", None)


def get_tokens(request: Request) -> TokenRegistry:
    return request.app.state.tokens


def require_token(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    tokens: TokenRegistry = request.app.state.tokens
    if cred is None or not tokens.is_valid(cred.credentials):
        raise HTTPException(status_code=401, detail="invalid or missing token")
```

`server/backend/app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import TokenRegistry
from ..deps import get_tokens

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request,
          tokens: TokenRegistry = Depends(get_tokens)) -> dict:
    if body.password != request.app.state.settings.admin_password:
        raise HTTPException(status_code=401, detail="wrong password")
    return {"token": tokens.issue()}
```

`server/backend/app/main.py`:
```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .auth import TokenRegistry
from .config import Settings, get_settings
from .routers import auth as auth_router
from .simulator.rig import NODE_IDS, SimRig
from .store import Store


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(Path(settings.data_file))
        store.load()
        app.state.settings = settings
        app.state.store = store
        app.state.tokens = TokenRegistry()
        if settings.transport_mode == "virtual":
            rig = SimRig.build(settings)
            await rig.start()
            app.state.rig = rig
            store.seed_nodes(list(NODE_IDS))
        else:  # serial 모드 — 하드웨어 전환 계획(스펙 §10)에서 구현
            app.state.rig = None
        store.save()
        yield
        if app.state.rig is not None:
            await app.state.rig.stop()
        store.save()

    app = FastAPI(title="E-FairBoard Server", lifespan=lifespan)
    app.include_router(auth_router.router)
    return app
```

`server/backend/app/routers/__init__.py`: 빈 파일.

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_auth.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app server/backend/tests
git commit -m "feat(api): FastAPI 앱 뼈대·단일 관리자 로그인·가상 모드 lifespan 조립"
```

---

### Task 13: 게시물 CRUD + 템플릿 라우터

**Files:**
- Create: `server/backend/app/schemas.py`
- Create: `server/backend/app/routers/posts.py`
- Modify: `server/backend/app/main.py` (라우터 2줄 추가)
- Test: `server/backend/tests/test_posts_api.py`

**Interfaces:**
- Consumes: `Store`(Task 11), `require_token`(Task 12), `TEMPLATES/as_dict`(Task 8)
- Produces (`app.schemas`): `PostCreate(title:str, template_id:int, fields:dict[str,str]={}, qr_url:str="")` — validator: `template_id`가 TEMPLATES에 존재, 각 `fields`의 key가 해당 템플릿 field id(str)이고 value의 UTF-8 길이가 `max_bytes` 이하, `qr_url` UTF-8 ≤ 198B. 위반 시 ValueError(→FastAPI 422)
- Produces (API, 모두 `require_token`):
  - `GET /api/templates` → `as_dict()` 결과
  - `GET /api/posts` → `list[Post]` (id 내림차순) / `POST /api/posts` (PostCreate) → 201 Post
  - `GET /api/posts/{id}` → Post / 404 · `PUT /api/posts/{id}` (PostCreate) → Post / 404 · `DELETE /api/posts/{id}` → 204 / 404

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_posts_api.py`

```python
VALID = {"title": "행사 안내", "template_id": 0,
         "fields": {"0": "임베디드 대회", "1": "7/20 10:00"},
         "qr_url": "https://4this.io"}


def test_requires_auth(client):
    assert client.get("/api/posts").status_code == 401


def test_templates_endpoint(client, auth_headers):
    res = client.get("/api/templates", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()) == 4


def test_create_and_get_post(client, auth_headers):
    res = client.post("/api/posts", json=VALID, headers=auth_headers)
    assert res.status_code == 201
    pid = res.json()["id"]
    got = client.get(f"/api/posts/{pid}", headers=auth_headers).json()
    assert got["title"] == "행사 안내"
    assert got["fields"]["0"] == "임베디드 대회"


def test_create_rejects_unknown_template(client, auth_headers):
    bad = dict(VALID, template_id=9)
    assert client.post("/api/posts", json=bad,
                       headers=auth_headers).status_code == 422


def test_create_rejects_field_over_max_bytes(client, auth_headers):
    bad = dict(VALID, fields={"0": "가" * 30})  # 90B > 제목 60B
    assert client.post("/api/posts", json=bad,
                       headers=auth_headers).status_code == 422


def test_create_rejects_unknown_field_id(client, auth_headers):
    bad = dict(VALID, fields={"7": "x"})
    assert client.post("/api/posts", json=bad,
                       headers=auth_headers).status_code == 422


def test_update_post(client, auth_headers):
    pid = client.post("/api/posts", json=VALID, headers=auth_headers).json()["id"]
    res = client.put(f"/api/posts/{pid}", json=dict(VALID, title="수정됨"),
                     headers=auth_headers)
    assert res.status_code == 200 and res.json()["title"] == "수정됨"


def test_delete_post(client, auth_headers):
    pid = client.post("/api/posts", json=VALID, headers=auth_headers).json()["id"]
    assert client.delete(f"/api/posts/{pid}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/posts/{pid}", headers=auth_headers).status_code == 404


def test_posts_persist_across_restart(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import TEST_PASSWORD, make_settings

    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as c1:
        token = c1.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
        c1.post("/api/posts", json=VALID,
                headers={"Authorization": f"Bearer {token}"})
    with TestClient(create_app(settings)) as c2:
        token = c2.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
        posts = c2.get("/api/posts",
                       headers={"Authorization": f"Bearer {token}"}).json()
        assert len(posts) == 1  # JSON 스냅샷에서 복원됨
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_posts_api.py -v`
Expected: FAIL — 401이 아니라 404(라우터 없음) 또는 ImportError

- [ ] **Step 3: 구현**

`server/backend/app/schemas.py`:
```python
from pydantic import BaseModel, field_validator, model_validator

from .protocol.templates import TEMPLATES

_MAX_TEXT_BYTES = 198  # SET_FIELD/SET_QR text 한도 (Task 4와 동일)


class PostCreate(BaseModel):
    title: str
    template_id: int
    fields: dict[str, str] = {}
    qr_url: str = ""

    @field_validator("template_id")
    @classmethod
    def template_must_exist(cls, v: int) -> int:
        if v not in TEMPLATES:
            raise ValueError(f"unknown template_id {v}")
        return v

    @field_validator("qr_url")
    @classmethod
    def qr_url_fits_payload(cls, v: str) -> str:
        if len(v.encode("utf-8")) > _MAX_TEXT_BYTES:
            raise ValueError("qr_url too long")
        return v

    @model_validator(mode="after")
    def fields_match_template(self) -> "PostCreate":
        tpl = TEMPLATES[self.template_id]
        defs = {str(f.id): f for f in tpl.fields}
        for key, text in self.fields.items():
            if key not in defs:
                raise ValueError(f"template {self.template_id} has no field {key}")
            if len(text.encode("utf-8")) > defs[key].max_bytes:
                raise ValueError(f"field {key} exceeds {defs[key].max_bytes} bytes")
        return self
```

`server/backend/app/routers/posts.py`:
```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from ..deps import get_store, require_token
from ..models import Post
from ..protocol.templates import as_dict
from ..schemas import PostCreate
from ..store import Store

router = APIRouter(prefix="/api", tags=["posts"],
                   dependencies=[Depends(require_token)])


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/templates")
def list_templates() -> list[dict]:
    return as_dict()


@router.get("/posts")
def list_posts(store: Store = Depends(get_store)) -> list[Post]:
    return sorted(store.state.posts.values(), key=lambda p: p.id, reverse=True)


@router.post("/posts", status_code=201)
def create_post(body: PostCreate, store: Store = Depends(get_store)) -> Post:
    pid = store.next_id("post")
    post = Post(id=pid, created_at=_now(), updated_at=_now(), **body.model_dump())
    store.state.posts[pid] = post
    store.save()
    return post


def _get_or_404(store: Store, post_id: int) -> Post:
    post = store.state.posts.get(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return post


@router.get("/posts/{post_id}")
def get_post(post_id: int, store: Store = Depends(get_store)) -> Post:
    return _get_or_404(store, post_id)


@router.put("/posts/{post_id}")
def update_post(post_id: int, body: PostCreate,
                store: Store = Depends(get_store)) -> Post:
    post = _get_or_404(store, post_id)
    updated = post.model_copy(update={**body.model_dump(), "updated_at": _now()})
    store.state.posts[post_id] = updated
    store.save()
    return updated


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: int, store: Store = Depends(get_store)) -> Response:
    _get_or_404(store, post_id)
    del store.state.posts[post_id]
    store.save()
    return Response(status_code=204)
```

`server/backend/app/main.py` 수정 — import에 `posts` 추가, `include_router` 아래에 한 줄:
```python
from .routers import auth as auth_router
from .routers import posts as posts_router
# ...
    app.include_router(auth_router.router)
    app.include_router(posts_router.router)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_posts_api.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app server/backend/tests/test_posts_api.py
git commit -m "feat(api): 게시물 CRUD·템플릿 조회 (필드 바이트 검증 포함)"
```

---

### Task 14: 노드 라우터 + 시뮬 제어 라우터

**Files:**
- Create: `server/backend/app/routers/nodes.py`
- Create: `server/backend/app/routers/sim.py`
- Modify: `server/backend/app/main.py` (라우터 2줄 추가)
- Test: `server/backend/tests/test_nodes_api.py`

**Interfaces:**
- Consumes: `SimRig`(Task 10 — `rig.nodes[id].display_state/powered`, `rig.channel.loss_rate/airtime_s`, `rig.link.request`), `Store`, `parse_pong`(Task 4)
- Produces (API, `require_token`):
  - `GET /api/nodes` → `list[NodeInfo]` (history 제외 — `model_dump(exclude={"history"})`)
  - `GET /api/nodes/{id}` → `NodeInfo + display_state` (가상 모드: rig에서 즉석 조회, serial 모드: `display_state=None`) / 404
  - `GET /api/nodes/{id}/history` → `list[StatusSample]`
  - `POST /api/nodes/{id}/ping` → PING 전송, 성공 시 `{"ok": true, "batt_mv": int, "rssi": int}` + NodeInfo 갱신(online·batt·last_seen), 타임아웃 시 `{"ok": false}` + offline 마킹
  - `GET /api/sim/config` → `{"loss_rate": float, "airtime_s": float}` / `PUT /api/sim/config` (동일 형태 부분 업데이트) — 가상 모드 아니면 409
  - `POST /api/sim/nodes/{id}/power` body `{"powered": bool}` → 노드 전원 토글 — 가상 모드 아니면 409
- Produces (`app.routers.nodes`): `async def ping_node(node_id, rig, store) -> dict` — deploy/모니터링(Task 17)이 재사용할 헬퍼 아님(각자 link 직접 사용). 라우터 전용

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_nodes_api.py`

```python
def test_nodes_seeded_in_virtual_mode(client, auth_headers):
    nodes = client.get("/api/nodes", headers=auth_headers).json()
    assert {n["id"] for n in nodes} == {1, 2}
    assert all("history" not in n for n in nodes)


def test_node_detail_includes_display_state(client, auth_headers):
    res = client.get("/api/nodes/1", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["display_state"]["template_id"] is None  # 아직 배포 없음


def test_node_detail_404(client, auth_headers):
    assert client.get("/api/nodes/99", headers=auth_headers).status_code == 404


def test_ping_marks_node_online(client, auth_headers):
    res = client.post("/api/nodes/1/ping", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True and body["batt_mv"] > 3000
    node = client.get("/api/nodes/1", headers=auth_headers).json()
    assert node["status"] == "online"


def test_ping_powered_off_marks_offline(client, auth_headers):
    client.post("/api/sim/nodes/1/power", json={"powered": False},
                headers=auth_headers)
    res = client.post("/api/nodes/1/ping", headers=auth_headers)
    assert res.json()["ok"] is False
    node = client.get("/api/nodes/1", headers=auth_headers).json()
    assert node["status"] == "offline"


def test_sim_config_roundtrip(client, auth_headers):
    client.put("/api/sim/config", json={"loss_rate": 0.3}, headers=auth_headers)
    cfg = client.get("/api/sim/config", headers=auth_headers).json()
    assert cfg["loss_rate"] == 0.3


def test_history_endpoint_empty_initially(client, auth_headers):
    assert client.get("/api/nodes/1/history", headers=auth_headers).json() == []
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_nodes_api.py -v`
Expected: FAIL — 404 (라우터 없음)

- [ ] **Step 3: 구현**

`server/backend/app/routers/nodes.py`:
```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_rig, get_store, require_token
from ..models import NodeInfo, StatusSample
from ..protocol.link import LinkError
from ..protocol.packet import MsgType, parse_pong
from ..store import Store

router = APIRouter(prefix="/api/nodes", tags=["nodes"],
                   dependencies=[Depends(require_token)])


def _get_or_404(store: Store, node_id: int) -> NodeInfo:
    node = store.state.nodes.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="node not found")
    return node


@router.get("")
def list_nodes(store: Store = Depends(get_store)) -> list[dict]:
    return [n.model_dump(exclude={"history"}, mode="json")
            for n in sorted(store.state.nodes.values(), key=lambda n: n.id)]


@router.get("/{node_id}")
def node_detail(node_id: int, store: Store = Depends(get_store),
                rig=Depends(get_rig)) -> dict:
    node = _get_or_404(store, node_id)
    data = node.model_dump(exclude={"history"}, mode="json")
    data["display_state"] = (
        rig.nodes[node_id].display_state
        if rig is not None and node_id in rig.nodes else None)
    return data


@router.get("/{node_id}/history")
def node_history(node_id: int, store: Store = Depends(get_store)) -> list[StatusSample]:
    return _get_or_404(store, node_id).history


@router.post("/{node_id}/ping")
async def ping_node(node_id: int, store: Store = Depends(get_store),
                    rig=Depends(get_rig)) -> dict:
    node = _get_or_404(store, node_id)
    if rig is None:
        raise HTTPException(status_code=409, detail="serial mode not implemented")
    try:
        pong = await rig.link.request(node_id, MsgType.PING, expect=MsgType.PONG)
    except LinkError:
        node.status = "offline"
        store.save()
        return {"ok": False}
    batt_mv, rssi, _status = parse_pong(pong.payload)
    now = datetime.now(timezone.utc)
    node.status = "online"
    node.batt_mv = batt_mv
    node.rssi = rssi
    node.last_seen_at = now
    store.add_history(node_id, StatusSample(t=now, batt_mv=batt_mv, rssi=rssi))
    store.save()
    return {"ok": True, "batt_mv": batt_mv, "rssi": rssi}
```

`server/backend/app/routers/sim.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_rig, require_token

router = APIRouter(prefix="/api/sim", tags=["sim"],
                   dependencies=[Depends(require_token)])


def _require_rig(rig):
    if rig is None:
        raise HTTPException(status_code=409, detail="not in virtual mode")
    return rig


class SimConfig(BaseModel):
    loss_rate: float | None = None
    airtime_s: float | None = None


class PowerBody(BaseModel):
    powered: bool


@router.get("/config")
def get_config(rig=Depends(get_rig)) -> dict:
    rig = _require_rig(rig)
    return {"loss_rate": rig.channel.loss_rate, "airtime_s": rig.channel.airtime_s}


@router.put("/config")
def put_config(body: SimConfig, rig=Depends(get_rig)) -> dict:
    rig = _require_rig(rig)
    if body.loss_rate is not None:
        rig.channel.loss_rate = body.loss_rate
    if body.airtime_s is not None:
        rig.channel.airtime_s = body.airtime_s
    return {"loss_rate": rig.channel.loss_rate, "airtime_s": rig.channel.airtime_s}


@router.post("/nodes/{node_id}/power")
def set_power(node_id: int, body: PowerBody, rig=Depends(get_rig)) -> dict:
    rig = _require_rig(rig)
    if node_id not in rig.nodes:
        raise HTTPException(status_code=404, detail="node not found")
    rig.nodes[node_id].powered = body.powered
    return {"node_id": node_id, "powered": body.powered}
```

`server/backend/app/main.py` 수정 — import·등록 추가:
```python
from .routers import nodes as nodes_router
from .routers import sim as sim_router
# ...
    app.include_router(nodes_router.router)
    app.include_router(sim_router.router)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_nodes_api.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app server/backend/tests/test_nodes_api.py
git commit -m "feat(api): 노드 조회·PING·시뮬 제어(손실률/전원 토글) 라우터"
```

---

### Task 15: 배포 파이프라인 (서비스 + 라우터)

**Files:**
- Create: `server/backend/app/services/__init__.py` (빈 파일)
- Create: `server/backend/app/services/deploy_service.py`
- Create: `server/backend/app/routers/deployments.py`
- Modify: `server/backend/app/main.py` (라우터 1줄 추가)
- Test: `server/backend/tests/test_deployments_api.py`

**Interfaces:**
- Consumes: `LinkManager.request`(Task 7), `Packet 빌더`(Task 4), `TEMPLATES`(Task 8), `Store/모델`(Task 11), `SimRig`(Task 10)
- Produces (`app.services.deploy_service`):
  - `def build_packet_plan(post: Post) -> list[tuple[MsgType, bytes]]` — `[(SET_TEMPLATE, b"\x{tid}"), (SET_FIELD, ...)*n, (SET_QR, ...)?, (COMMIT, b"\x{mode}")]` 순서. `qr_url`이 빈 문자열이면 SET_QR 생략. COMMIT의 refresh_mode는 호출자가 마지막에 덧붙임 — 시그니처를 `build_packet_plan(post: Post, refresh_mode: int) -> list[...]`로 하고 COMMIT까지 포함해 반환
  - `async def run_deployment(store: Store, rig: SimRig, deployment_id: int) -> None` — 각 target 순차 처리: `status="sending"` → 패킷 플랜을 순서대로 `link.request(..., expect=ACK)` (패킷 단위 재시도는 link가 소유, `target.attempts`는 시도한 패킷 수). 전 패킷 성공 시 target `success`+`acked_at` 기록+해당 노드 `current_post_id`·online 갱신, `LinkError` 발생 시 target `failed`+`error` 기록+노드 offline 마킹 후 다음 target으로. 전 target 종료 후 Deployment.status = 전부 성공 `success` / 일부 `partial` / 전부 실패 `failed`, `finished_at` 기록, `store.save()`
  - `def start_deployment(store, rig, post_id, node_ids, refresh_mode, trigger) -> Deployment` — 검증(post 존재·node 존재, 아니면 ValueError), Deployment 생성·저장 후 `asyncio.create_task(run_deployment(...))` 기동, 생성된 Deployment 반환
- Produces (API, `require_token`):
  - `POST /api/deployments` body `{"post_id": int, "node_ids": [int] | "all", "refresh_mode": 0|1}` → 202 `Deployment` / 404(post·node 없음)
  - `GET /api/deployments/{id}` → Deployment / 404 — **진행 중 1초 폴링 대상**
  - `GET /api/deployments` → `list[Deployment]` (id 내림차순)

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_deployments_api.py`

```python
import time

VALID_POST = {"title": "행사", "template_id": 0,
              "fields": {"0": "제목", "1": "일시"}, "qr_url": "https://x.io"}


def make_post(client, auth_headers) -> int:
    return client.post("/api/posts", json=VALID_POST,
                       headers=auth_headers).json()["id"]


def wait_deployment(client, auth_headers, dep_id, timeout=5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dep = client.get(f"/api/deployments/{dep_id}",
                         headers=auth_headers).json()
        if dep["status"] != "running":
            return dep
        time.sleep(0.02)
    raise AssertionError("deployment did not finish")


def test_deploy_to_all_nodes_success(client, auth_headers):
    pid = make_post(client, auth_headers)
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": "all", "refresh_mode": 0},
                      headers=auth_headers)
    assert res.status_code == 202
    dep = wait_deployment(client, auth_headers, res.json()["id"])
    assert dep["status"] == "success"
    assert {t["node_id"] for t in dep["targets"]} == {1, 2}
    assert all(t["status"] == "success" for t in dep["targets"])
    # 노드 화면·current_post_id 반영 확인
    node = client.get("/api/nodes/1", headers=auth_headers).json()
    assert node["current_post_id"] == pid
    assert node["display_state"]["fields"]["0"] == "제목"


def test_deploy_single_node(client, auth_headers):
    pid = make_post(client, auth_headers)
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": [2], "refresh_mode": 1},
                      headers=auth_headers)
    dep = wait_deployment(client, auth_headers, res.json()["id"])
    assert [t["node_id"] for t in dep["targets"]] == [2]
    node1 = client.get("/api/nodes/1", headers=auth_headers).json()
    assert node1["display_state"]["template_id"] is None  # 노드1은 미배포


def test_deploy_partial_when_one_node_off(client, auth_headers):
    client.post("/api/sim/nodes/2/power", json={"powered": False},
                headers=auth_headers)
    pid = make_post(client, auth_headers)
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": "all", "refresh_mode": 0},
                      headers=auth_headers)
    dep = wait_deployment(client, auth_headers, res.json()["id"])
    assert dep["status"] == "partial"
    by_node = {t["node_id"]: t for t in dep["targets"]}
    assert by_node[1]["status"] == "success"
    assert by_node[2]["status"] == "failed" and by_node[2]["error"]
    node2 = client.get("/api/nodes/2", headers=auth_headers).json()
    assert node2["status"] == "offline"


def test_deploy_unknown_post_404(client, auth_headers):
    res = client.post("/api/deployments",
                      json={"post_id": 999, "node_ids": "all", "refresh_mode": 0},
                      headers=auth_headers)
    assert res.status_code == 404


def test_running_deployment_marked_failed_on_boot(tmp_path):
    """서버가 배포 도중 죽었다 재시작하면 running → failed(interrupted) (스펙 §7)."""
    from datetime import datetime, timezone

    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.models import Deployment, DeployTarget
    from app.store import Store
    from tests.conftest import TEST_PASSWORD, make_settings

    settings = make_settings(tmp_path)
    store = Store(tmp_path / "state.json")
    store.load()
    store.state.deployments[1] = Deployment(
        id=1, post_id=1, status="running",
        created_at=datetime.now(timezone.utc),
        targets=[DeployTarget(node_id=1, status="sending")])
    store.state.next_deployment_id = 2
    store.save()

    with TestClient(create_app(settings)) as c:
        token = c.post("/api/auth/login",
                       json={"password": TEST_PASSWORD}).json()["token"]
        dep = c.get("/api/deployments/1",
                    headers={"Authorization": f"Bearer {token}"}).json()
    assert dep["status"] == "failed"
    assert dep["targets"][0]["status"] == "failed"
    assert dep["targets"][0]["error"] == "interrupted"


def test_deployment_list_ordering(client, auth_headers):
    pid = make_post(client, auth_headers)
    ids = []
    for _ in range(2):
        res = client.post("/api/deployments",
                          json={"post_id": pid, "node_ids": [1], "refresh_mode": 0},
                          headers=auth_headers)
        ids.append(res.json()["id"])
        wait_deployment(client, auth_headers, ids[-1])
    listed = client.get("/api/deployments", headers=auth_headers).json()
    assert [d["id"] for d in listed][:2] == sorted(ids, reverse=True)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_deployments_api.py -v`
Expected: FAIL — 404 (라우터 없음)

- [ ] **Step 3: 구현**

`server/backend/app/services/deploy_service.py`:
```python
import asyncio
from datetime import datetime, timezone
from typing import Literal

from ..models import Deployment, DeployTarget, Post
from ..protocol.link import LinkError
from ..protocol.packet import MsgType, build_set_field, build_set_qr
from ..simulator.rig import SimRig
from ..store import Store


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_packet_plan(post: Post, refresh_mode: int) -> list[tuple[MsgType, bytes]]:
    """게시물 → SET_TEMPLATE → SET_FIELD×n → SET_QR? → COMMIT (PROTOCOL.md §4)."""
    plan: list[tuple[MsgType, bytes]] = [
        (MsgType.SET_TEMPLATE, bytes([post.template_id]))]
    for field_id in sorted(post.fields, key=int):
        plan.append((MsgType.SET_FIELD,
                     build_set_field(int(field_id), post.fields[field_id])))
    if post.qr_url:
        plan.append((MsgType.SET_QR, build_set_qr(post.qr_url)))
    plan.append((MsgType.COMMIT, bytes([refresh_mode])))
    return plan


def start_deployment(store: Store, rig: SimRig, *, post_id: int,
                     node_ids: list[int], refresh_mode: int,
                     trigger: Literal["manual", "scheduled"]) -> Deployment:
    if post_id not in store.state.posts:
        raise ValueError("post not found")
    for nid in node_ids:
        if nid not in store.state.nodes:
            raise ValueError(f"node {nid} not found")
    dep = Deployment(
        id=store.next_id("deployment"), post_id=post_id, trigger=trigger,
        refresh_mode=refresh_mode, created_at=_now(),
        targets=[DeployTarget(node_id=nid) for nid in node_ids])
    store.state.deployments[dep.id] = dep
    store.save()
    asyncio.get_running_loop().create_task(run_deployment(store, rig, dep.id))
    return dep


async def run_deployment(store: Store, rig: SimRig, deployment_id: int) -> None:
    dep = store.state.deployments[deployment_id]
    post = store.state.posts[dep.post_id]
    plan = build_packet_plan(post, dep.refresh_mode)
    for target in dep.targets:  # 순차 유니캐스트 (스펙 §5.5)
        target.status = "sending"
        store.save()
        try:
            for msg_type, payload in plan:
                target.attempts += 1
                await rig.link.request(target.node_id, msg_type, payload,
                                       expect=MsgType.ACK)
            target.status = "success"
            target.acked_at = _now()
            node = store.state.nodes[target.node_id]
            node.current_post_id = post.id
            node.status = "online"
            node.last_seen_at = _now()
        except LinkError as exc:
            target.status = "failed"
            target.error = str(exc)
            store.state.nodes[target.node_id].status = "offline"
        store.save()
    statuses = {t.status for t in dep.targets}
    dep.status = ("success" if statuses == {"success"}
                  else "failed" if statuses == {"failed"} else "partial")
    dep.finished_at = _now()
    store.save()
```

`server/backend/app/routers/deployments.py`:
```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_rig, get_store, require_token
from ..models import Deployment
from ..services.deploy_service import start_deployment
from ..store import Store

router = APIRouter(prefix="/api/deployments", tags=["deployments"],
                   dependencies=[Depends(require_token)])


class DeployBody(BaseModel):
    post_id: int
    node_ids: list[int] | Literal["all"]
    refresh_mode: Literal[0, 1] = 0


@router.post("", status_code=202)
async def create_deployment(body: DeployBody, store: Store = Depends(get_store),
                            rig=Depends(get_rig)) -> Deployment:
    # async 필수: start_deployment가 실행 중인 이벤트 루프에 태스크를 건다
    if rig is None:
        raise HTTPException(status_code=409, detail="serial mode not implemented")
    node_ids = (sorted(store.state.nodes) if body.node_ids == "all"
                else body.node_ids)
    try:
        return start_deployment(store, rig, post_id=body.post_id,
                                node_ids=node_ids,
                                refresh_mode=body.refresh_mode, trigger="manual")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{deployment_id}")
def get_deployment(deployment_id: int,
                   store: Store = Depends(get_store)) -> Deployment:
    dep = store.state.deployments.get(deployment_id)
    if dep is None:
        raise HTTPException(status_code=404, detail="deployment not found")
    return dep


@router.get("")
def list_deployments(store: Store = Depends(get_store)) -> list[Deployment]:
    return sorted(store.state.deployments.values(),
                  key=lambda d: d.id, reverse=True)
```

`server/backend/app/main.py` 수정 — 라우터 등록 + 재시작 정리(스펙 §7):
```python
from datetime import datetime, timezone

from .routers import deployments as deployments_router

# lifespan 안, store.load() 직후에 추가 — 배포 도중 죽었던 흔적 정리:
        for dep in store.state.deployments.values():
            if dep.status == "running":
                dep.status = "failed"
                dep.finished_at = datetime.now(timezone.utc)
                for target in dep.targets:
                    if target.status in ("pending", "sending"):
                        target.status = "failed"
                        target.error = "interrupted"

# 라우터 등록:
    app.include_router(deployments_router.router)
```

`server/backend/app/services/__init__.py`: 빈 파일.

- [ ] **Step 4: 통과 확인 (전체 회귀 포함)**

Run: `python -m pytest -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app server/backend/tests/test_deployments_api.py
git commit -m "feat(deploy): 배포 파이프라인 — 순차 유니캐스트·partial 판정·오프라인 마킹"
```

---

### Task 16: 예약 배포 (APScheduler)

**Files:**
- Create: `server/backend/app/services/schedule_service.py`
- Create: `server/backend/app/routers/schedules.py`
- Modify: `server/backend/app/main.py` (ScheduleService lifespan 통합 + 라우터 1줄)
- Test: `server/backend/tests/test_schedules_api.py`

**Interfaces:**
- Consumes: `start_deployment`(Task 15), `Store/Schedule`(Task 11)
- Produces (`app.services.schedule_service`): `class ScheduleService`
  - `__init__(self, store: Store, rig)` — `AsyncIOScheduler`(인메모리 jobstore) 생성
  - `def start(self) -> None` — 스케줄러 시작 + **JSON에서 복원**: `pending` Schedule을 전부 `_register`(과거 `run_at`은 즉시 실행되도록 `misfire_grace_time=None` 대신 `next_run_time=now` 처리 — APScheduler `date` 트리거에 과거 시각을 주면 misfire되므로, 과거면 `run_at=now+1s`로 보정해 등록)
  - `def shutdown(self) -> None`
  - `def add(self, post_id: int, node_ids: list[int], run_at: datetime) -> Schedule` — 검증(post·node 존재, `ValueError`), Schedule 저장 + job 등록(`job_id=f"schedule-{id}"`)
  - `def cancel(self, schedule_id: int) -> None` — `pending`만 취소 가능(`ValueError`), job 제거 + `status="cancelled"`
  - `async def _fire(self, schedule_id: int) -> None` — `pending` 확인 후 `start_deployment(..., trigger="scheduled")`, `status="done"`, save. post가 그 사이 삭제됐으면 `status="done"` 처리하되 배포는 생략
- Produces (API, `require_token`):
  - `POST /api/schedules` body `{"post_id": int, "node_ids": [int]|"all", "run_at": ISO8601}` → 201 Schedule / 404
  - `GET /api/schedules` → `list[Schedule]` (run_at 오름차순) · `DELETE /api/schedules/{id}` → 204 / 404 / 409(취소 불가 상태)

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_schedules_api.py`

```python
import time
from datetime import datetime, timedelta, timezone

VALID_POST = {"title": "예약", "template_id": 0, "fields": {"0": "T"},
              "qr_url": ""}


def make_post(client, auth_headers) -> int:
    return client.post("/api/posts", json=VALID_POST,
                       headers=auth_headers).json()["id"]


def in_seconds(s: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=s)).isoformat()


def test_create_and_list_schedule(client, auth_headers):
    pid = make_post(client, auth_headers)
    res = client.post("/api/schedules",
                      json={"post_id": pid, "node_ids": [1],
                            "run_at": in_seconds(3600)},
                      headers=auth_headers)
    assert res.status_code == 201
    listed = client.get("/api/schedules", headers=auth_headers).json()
    assert listed[0]["status"] == "pending"


def test_schedule_fires_and_deploys(client, auth_headers):
    pid = make_post(client, auth_headers)
    client.post("/api/schedules",
                json={"post_id": pid, "node_ids": "all",
                      "run_at": in_seconds(0.2)},
                headers=auth_headers)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        deps = client.get("/api/deployments", headers=auth_headers).json()
        if deps and deps[0]["status"] == "success":
            break
        time.sleep(0.05)
    else:
        raise AssertionError("scheduled deployment did not run")
    assert deps[0]["trigger"] == "scheduled"
    sched = client.get("/api/schedules", headers=auth_headers).json()[0]
    assert sched["status"] == "done"


def test_cancel_schedule(client, auth_headers):
    pid = make_post(client, auth_headers)
    sid = client.post("/api/schedules",
                      json={"post_id": pid, "node_ids": [1],
                            "run_at": in_seconds(3600)},
                      headers=auth_headers).json()["id"]
    assert client.delete(f"/api/schedules/{sid}",
                         headers=auth_headers).status_code == 204
    sched = client.get("/api/schedules", headers=auth_headers).json()[0]
    assert sched["status"] == "cancelled"


def test_schedule_unknown_post_404(client, auth_headers):
    res = client.post("/api/schedules",
                      json={"post_id": 999, "node_ids": [1],
                            "run_at": in_seconds(60)},
                      headers=auth_headers)
    assert res.status_code == 404


def test_pending_schedule_restored_after_restart(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.conftest import TEST_PASSWORD, make_settings

    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as c1:
        token = c1.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        pid = c1.post("/api/posts", json=VALID_POST, headers=h).json()["id"]
        c1.post("/api/schedules",
                json={"post_id": pid, "node_ids": [1],
                      "run_at": in_seconds(0.2)}, headers=h)
    # 재시작 — pending 예약이 부팅 시 재등록되어 실행된다
    with TestClient(create_app(settings)) as c2:
        token = c2.post("/api/auth/login",
                        json={"password": TEST_PASSWORD}).json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            deps = c2.get("/api/deployments", headers=h).json()
            if deps and deps[0]["status"] != "running":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("restored schedule did not fire")
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_schedules_api.py -v`
Expected: FAIL — 404 (라우터 없음)

- [ ] **Step 3: 구현**

`server/backend/app/services/schedule_service.py`:
```python
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..models import Schedule
from ..store import Store
from .deploy_service import start_deployment


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScheduleService:
    """일회성 예약 — 인메모리 jobstore, 부팅 시 JSON에서 pending 재등록 (스펙 §5.3)."""

    def __init__(self, store: Store, rig) -> None:
        self._store = store
        self._rig = rig
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        self._scheduler.start()
        for sched in self._store.state.schedules.values():
            if sched.status == "pending":
                self._register(sched)

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _register(self, sched: Schedule) -> None:
        run_at = sched.run_at
        if run_at <= _now():  # 서버 꺼진 사이 지난 예약 → 즉시 실행으로 보정
            run_at = _now() + timedelta(seconds=1)
        self._scheduler.add_job(self._fire, "date", run_date=run_at,
                                args=[sched.id], id=f"schedule-{sched.id}")

    def add(self, post_id: int, node_ids: list[int], run_at: datetime) -> Schedule:
        if post_id not in self._store.state.posts:
            raise ValueError("post not found")
        for nid in node_ids:
            if nid not in self._store.state.nodes:
                raise ValueError(f"node {nid} not found")
        sched = Schedule(id=self._store.next_id("schedule"), post_id=post_id,
                         node_ids=node_ids, run_at=run_at, created_at=_now())
        self._store.state.schedules[sched.id] = sched
        self._store.save()
        self._register(sched)
        return sched

    def cancel(self, schedule_id: int) -> None:
        sched = self._store.state.schedules.get(schedule_id)
        if sched is None:
            raise KeyError(schedule_id)
        if sched.status != "pending":
            raise ValueError("only pending schedules can be cancelled")
        job = self._scheduler.get_job(f"schedule-{schedule_id}")
        if job is not None:
            job.remove()
        sched.status = "cancelled"
        self._store.save()

    async def _fire(self, schedule_id: int) -> None:
        sched = self._store.state.schedules.get(schedule_id)
        if sched is None or sched.status != "pending":
            return
        sched.status = "done"
        if sched.post_id in self._store.state.posts:
            start_deployment(self._store, self._rig, post_id=sched.post_id,
                             node_ids=sched.node_ids, refresh_mode=0,
                             trigger="scheduled")
        self._store.save()
```

`server/backend/app/routers/schedules.py`:
```python
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..deps import get_store, require_token
from ..models import Schedule
from ..store import Store

router = APIRouter(prefix="/api/schedules", tags=["schedules"],
                   dependencies=[Depends(require_token)])


class ScheduleBody(BaseModel):
    post_id: int
    node_ids: list[int] | Literal["all"]
    run_at: datetime


@router.post("", status_code=201)
def create_schedule(body: ScheduleBody, request: Request,
                    store: Store = Depends(get_store)) -> Schedule:
    service = request.app.state.schedule_service
    node_ids = (sorted(store.state.nodes) if body.node_ids == "all"
                else body.node_ids)
    try:
        return service.add(body.post_id, node_ids, body.run_at)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("")
def list_schedules(store: Store = Depends(get_store)) -> list[Schedule]:
    return sorted(store.state.schedules.values(), key=lambda s: s.run_at)


@router.delete("/{schedule_id}", status_code=204)
def cancel_schedule(schedule_id: int, request: Request) -> Response:
    service = request.app.state.schedule_service
    try:
        service.cancel(schedule_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="schedule not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)
```

`server/backend/app/main.py` 수정 — lifespan에 ScheduleService 통합:
```python
from .routers import schedules as schedules_router
from .services.schedule_service import ScheduleService
# lifespan 안, rig 조립 뒤에:
        schedule_service = ScheduleService(store, app.state.rig)
        schedule_service.start()
        app.state.schedule_service = schedule_service
# yield 뒤 정리(rig stop 앞):
        schedule_service.shutdown()
# 라우터 등록:
    app.include_router(schedules_router.router)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_schedules_api.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app server/backend/tests/test_schedules_api.py
git commit -m "feat(schedule): 일회성 예약 배포 — APScheduler 인메모리·재시작 복원"
```

---

### Task 17: 노드 모니터링 루프 + 통계 API

**Files:**
- Create: `server/backend/app/services/node_service.py`
- Create: `server/backend/app/services/stats_service.py`
- Create: `server/backend/app/routers/stats.py`
- Modify: `server/backend/app/main.py` (모니터 태스크 lifespan 통합 + 라우터 1줄)
- Test: `server/backend/tests/test_monitor_and_stats.py`

**Interfaces:**
- Consumes: `LinkManager.request`(Task 7), `parse_status_res`(Task 4), `Store`(Task 11)
- Produces (`app.services.node_service`): `class NodeMonitor(store, rig, interval_s)`
  - `async def start()` — 주기 루프 태스크 기동 / `async def stop()`
  - `async def poll_once() -> None` — 모든 노드에 STATUS_REQ: 성공 → `status="online"`, `batt_mv`·`last_seen_at` 갱신 + `add_history`(rssi는 PONG에만 있으므로 STATUS_RES 기반 샘플은 `rssi=node.rssi or -128`… **아니오, 단순화**: STATUS_RES에는 rssi가 없으므로 history 샘플의 rssi는 기존 값 유지 없으면 0). `LinkError` → **2회 연속 실패 시** `status="offline"` (내부 `_miss_count: dict[int,int]`). 각 폴 후 `store.save()`
- Produces (`app.services.stats_service`): `def summary(store: Store) -> dict` — `{"deployments_total": int, "targets_total": int, "targets_success": int, "success_rate": float(0~1, 타깃 없으면 1.0), "paper_saved": int(성공 타깃 수 = 대체된 종이 1장/회, 스펙 §5.4), "nodes_online": int, "nodes_total": int}`
- Produces (API): `GET /api/stats/summary`(require_token) → 위 dict

- [ ] **Step 1: 실패하는 테스트 작성** — `server/backend/tests/test_monitor_and_stats.py`

모니터 자동 루프는 테스트 설정에서 1시간 주기(사실상 비활성)이므로, `poll_once()`를 직접 호출해 검증한다. TestClient(동기)와 asyncio가 섞이지 않도록 monitor 단위 테스트는 SimRig을 직접 조립한다.

```python
import pytest

from app.config import Settings
from app.services.node_service import NodeMonitor
from app.services.stats_service import summary
from app.simulator.rig import SimRig
from app.store import Store


def fast_settings(tmp_path) -> Settings:
    return Settings(_env_file=None, sim_airtime_s=0.0, ack_timeout_s=0.05,
                    sim_refresh_partial_s=0.0, sim_refresh_full_s=0.0,
                    data_file=str(tmp_path / "state.json"))


@pytest.fixture
async def rig_and_store(tmp_path):
    settings = fast_settings(tmp_path)
    rig = SimRig.build(settings)
    await rig.start()
    store = Store(tmp_path / "state.json")
    store.load()
    store.seed_nodes([0x01, 0x02])
    yield rig, store
    await rig.stop()


async def test_poll_once_marks_online_and_appends_history(rig_and_store):
    rig, store = rig_and_store
    monitor = NodeMonitor(store, rig, interval_s=3600)
    await monitor.poll_once()
    node = store.state.nodes[0x01]
    assert node.status == "online"
    assert node.batt_mv and node.batt_mv > 3000
    assert len(node.history) == 1


async def test_two_consecutive_misses_mark_offline(rig_and_store):
    rig, store = rig_and_store
    monitor = NodeMonitor(store, rig, interval_s=3600)
    rig.nodes[0x02].powered = False
    await monitor.poll_once()
    assert store.state.nodes[0x02].status != "offline"  # 1회 실패는 유예
    await monitor.poll_once()
    assert store.state.nodes[0x02].status == "offline"


async def test_success_resets_miss_count(rig_and_store):
    rig, store = rig_and_store
    monitor = NodeMonitor(store, rig, interval_s=3600)
    rig.nodes[0x01].powered = False
    await monitor.poll_once()
    rig.nodes[0x01].powered = True
    await monitor.poll_once()
    rig.nodes[0x01].powered = False
    await monitor.poll_once()
    assert store.state.nodes[0x01].status == "online"  # 아직 1회 실패


def test_stats_summary_counts(client, auth_headers):
    post = {"title": "T", "template_id": 0, "fields": {"0": "A"}, "qr_url": ""}
    pid = client.post("/api/posts", json=post, headers=auth_headers).json()["id"]
    import time
    res = client.post("/api/deployments",
                      json={"post_id": pid, "node_ids": "all", "refresh_mode": 0},
                      headers=auth_headers)
    dep_id = res.json()["id"]
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if client.get(f"/api/deployments/{dep_id}",
                      headers=auth_headers).json()["status"] != "running":
            break
        time.sleep(0.02)
    stats = client.get("/api/stats/summary", headers=auth_headers).json()
    assert stats["deployments_total"] == 1
    assert stats["targets_success"] == 2
    assert stats["paper_saved"] == 2
    assert stats["success_rate"] == 1.0
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_monitor_and_stats.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 구현**

`server/backend/app/services/node_service.py`:
```python
import asyncio
from datetime import datetime, timezone

from ..models import StatusSample
from ..protocol.link import LinkError
from ..protocol.packet import MsgType, parse_status_res
from ..store import Store

_OFFLINE_AFTER_MISSES = 2


class NodeMonitor:
    """주기적 STATUS_REQ 폴링 (스펙 §5.6). 실노드 딥슬립 주기와의 동기화는
    펌웨어 팀 협의 항목 — interval_s는 설정으로 주입."""

    def __init__(self, store: Store, rig, interval_s: float) -> None:
        self._store = store
        self._rig = rig
        self._interval_s = interval_s
        self._miss_count: dict[int, int] = {}
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval_s)
            await self.poll_once()

    async def poll_once(self) -> None:
        for node_id in sorted(self._store.state.nodes):
            node = self._store.state.nodes[node_id]
            try:
                res = await self._rig.link.request(
                    node_id, MsgType.STATUS_REQ, expect=MsgType.STATUS_RES)
            except LinkError:
                misses = self._miss_count.get(node_id, 0) + 1
                self._miss_count[node_id] = misses
                if misses >= _OFFLINE_AFTER_MISSES:
                    node.status = "offline"
                continue
            batt_mv, _last_seq, _uptime, _err = parse_status_res(res.payload)
            now = datetime.now(timezone.utc)
            self._miss_count[node_id] = 0
            node.status = "online"
            node.batt_mv = batt_mv
            node.last_seen_at = now
            self._store.add_history(node_id, StatusSample(
                t=now, batt_mv=batt_mv, rssi=node.rssi or 0))
        self._store.save()
```

`server/backend/app/services/stats_service.py`:
```python
from ..store import Store


def summary(store: Store) -> dict:
    deployments = store.state.deployments.values()
    targets = [t for d in deployments for t in d.targets]
    success = [t for t in targets if t.status == "success"]
    nodes = store.state.nodes.values()
    return {
        "deployments_total": len(store.state.deployments),
        "targets_total": len(targets),
        "targets_success": len(success),
        "success_rate": (len(success) / len(targets)) if targets else 1.0,
        "paper_saved": len(success),  # 성공 갱신 1회 = 종이 1장 대체 (스펙 §5.4)
        "nodes_online": sum(1 for n in nodes if n.status == "online"),
        "nodes_total": len(store.state.nodes),
    }
```

`server/backend/app/routers/stats.py`:
```python
from fastapi import APIRouter, Depends

from ..deps import get_store, require_token
from ..services.stats_service import summary
from ..store import Store

router = APIRouter(prefix="/api/stats", tags=["stats"],
                   dependencies=[Depends(require_token)])


@router.get("/summary")
def stats_summary(store: Store = Depends(get_store)) -> dict:
    return summary(store)
```

`server/backend/app/main.py` 수정 — lifespan에 NodeMonitor 통합:
```python
from .routers import stats as stats_router
from .services.node_service import NodeMonitor
# lifespan 안, schedule_service 다음:
        monitor = NodeMonitor(store, app.state.rig,
                              interval_s=settings.status_poll_interval_s)
        if app.state.rig is not None:
            await monitor.start()
        app.state.node_monitor = monitor
# yield 뒤 정리(schedule_service.shutdown() 앞):
        await monitor.stop()
# 라우터 등록:
    app.include_router(stats_router.router)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_monitor_and_stats.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add server/backend/app server/backend/tests/test_monitor_and_stats.py
git commit -m "feat(monitor,stats): STATUS 폴링 모니터(2회 유예 오프라인)·통계 요약"
```

---

### Task 18: 최종 E2E 시나리오 + 실행 문서

**Files:**
- Create: `server/backend/tests/test_full_scenario.py`
- Create: `server/backend/README.md`
- Modify: `server/backend/app/main.py` (프론트 정적 서빙 자리 — 조건부 mount)

**Interfaces:**
- Consumes: 전체 스택 (Task 1~17)
- Produces: 데모 시나리오를 그대로 재현하는 회귀 테스트 + 팀원용 실행 문서

- [ ] **Step 1: 최종 E2E 테스트 작성** — `server/backend/tests/test_full_scenario.py`

```python
import time

VALID_POST = {"title": "폐막식 안내", "template_id": 0,
              "fields": {"0": "폐막식", "1": "7/21 17:00", "2": "대강당"},
              "qr_url": "https://4this.io/closing"}


def wait_done(client, headers, dep_id, timeout=10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dep = client.get(f"/api/deployments/{dep_id}", headers=headers).json()
        if dep["status"] != "running":
            return dep
        time.sleep(0.02)
    raise AssertionError("deployment stuck")


def test_demo_scenario_end_to_end(client, auth_headers):
    """데모 시나리오: 손실 30% 설정 → 게시물 작성 → 일괄 배포 → 성공 →
    노드 화면 확인 → 통계 반영 → 노드 전원 차단 → 재배포 → partial."""
    h = auth_headers
    # 1) 악조건 설정 (재전송 경로 검증)
    client.put("/api/sim/config", json={"loss_rate": 0.3}, headers=h)
    # 2) 게시물 작성
    pid = client.post("/api/posts", json=VALID_POST, headers=h).json()["id"]
    # 3) 일괄 배포 → 성공
    dep_id = client.post("/api/deployments",
                         json={"post_id": pid, "node_ids": "all",
                               "refresh_mode": 1},
                         headers=h).json()["id"]
    assert wait_done(client, h, dep_id)["status"] == "success"
    # 4) 두 노드 화면 상태 일치
    for nid in (1, 2):
        state = client.get(f"/api/nodes/{nid}", headers=h).json()["display_state"]
        assert state["fields"]["0"] == "폐막식"
        assert state["qr_url"] == "https://4this.io/closing"
    # 5) 통계 반영
    stats = client.get("/api/stats/summary", headers=h).json()
    assert stats["paper_saved"] == 2 and stats["success_rate"] == 1.0
    # 6) 노드2 전원 차단 → 재배포 → partial
    client.post("/api/sim/nodes/2/power", json={"powered": False}, headers=h)
    dep2 = client.post("/api/deployments",
                       json={"post_id": pid, "node_ids": "all",
                             "refresh_mode": 0},
                       headers=h).json()["id"]
    result = wait_done(client, h, dep2)
    assert result["status"] == "partial"
    assert client.get("/api/nodes/2", headers=h).json()["status"] == "offline"
```

- [ ] **Step 2: 실행 후 확인**

Run: `python -m pytest tests/test_full_scenario.py -v`
Expected: PASS (1 passed) — 실패하면 해당 계층 태스크로 돌아가 수정

- [ ] **Step 3: 정적 서빙 자리 추가** — `server/backend/app/main.py`의 `create_app` 마지막(라우터 등록 뒤)에:

```python
from pathlib import Path as _Path

from fastapi.staticfiles import StaticFiles

# create_app 본문 마지막:
    dist = _Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.exists():  # 프론트 빌드 산출물이 있으면 단일 프로세스 데모 (스펙 §3)
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app
```

- [ ] **Step 4: README 작성** — `server/backend/README.md`

````markdown
# E-FairBoard 백엔드

하드웨어 없이 동작하는 가상 모드가 기본이다. `TRANSPORT_MODE=serial`은
하드웨어 도착 후 활성화(스펙 §10).

## 실행

```powershell
cd server/backend
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # ADMIN_PASSWORD 수정
uvicorn app.main:create_app --factory --reload --port 8000
```

- API 문서: http://localhost:8000/docs
- 로그인: `POST /api/auth/login {"password": "..."}` → 이후 `Authorization: Bearer <token>`
- 가상 노드 2개(0x01, 0x02)가 서버와 함께 뜬다. 손실률·전원은 `/api/sim/*`로 조작.

## 테스트

```powershell
python -m pytest -q
```

## 구조

`app/protocol`(패킷·CRC16·COBS·링크 — 펌웨어 레퍼런스), `app/transport`(가상/시리얼),
`app/simulator`(가상 게이트웨이·노드), `app/services`(배포·예약·모니터·통계),
`app/routers`(REST API), `app/store.py`(메모리+JSON 스냅샷).
설계 문서: `docs/web/2026-07-08-web-design.md`
````

- [ ] **Step 5: 전체 회귀 + 수동 스모크 확인**

Run: `python -m pytest -q`
Expected: 전부 PASS

수동 스모크 (별도 터미널):
```powershell
uvicorn app.main:create_app --factory --port 8000
# http://localhost:8000/docs 에서 login → posts 생성 → deployments 실행
# → GET /api/nodes/1 의 display_state 반영 확인
```

- [ ] **Step 6: 커밋**

```bash
git add server/backend
git commit -m "test(e2e): 데모 시나리오 회귀 테스트·README·정적 서빙 자리 추가"
```

---

## 이 계획이 다루지 않는 것 (후속 계획)

- **프론트엔드**(Vue 3 + TS + Element Plus, EpaperPreview 등) — 별도 계획 문서로 작성 (스펙 §6)
- **SerialTransport 실장** — 하드웨어 도착 후 (스펙 §10). `app/transport/serial_port.py` 자리는 그때 생성
- **펌웨어 팀 개발 지시서** — 이 계획의 `protocol/`·`simulator/node.py`·테스트 벡터가 재료 (스펙 §11)







