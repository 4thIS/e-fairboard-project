# server/ 백엔드 코어 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 게이트웨이 하드웨어 없이 E2E 검증 가능한 FastAPI 백엔드 코어(패킷 코덱 + 시리얼 브리지 + 모의 GW + REST + 예약).

**Architecture:** 계층형 모노리스 — protocol(순수 코덱) / bridge(Transport 추상) / core(상태·배포·예약) / api. 모의 게이트웨이(`sim/`)가 Transport 구현체로 끼워져 실물 도착 시 `SerialTransport`로만 교체.

**Tech Stack:** Python ≥3.12, uv, FastAPI, pyserial, APScheduler, pytest(+pytest-asyncio).

**스펙:** `docs/superpowers/specs/2026-07-08-server-skeleton-design.md`

## Global Constraints

- 모든 작업은 `server/` 디렉토리에서, `jp` 브랜치에서 수행. 명령은 `cd ~/e-fairboard-project/server` 후 실행.
- DB 금지 — 상태는 메모리 + `data/state.json` (원자적 쓰기: tmp + `os.replace`).
- 엔디안: **little-endian** (CRC16 wire 인코딩 포함). PAYLOAD ≤ 200B.
- CRC-16/CCITT-FALSE: poly `0x1021`, init `0xFFFF`, no reflect. 검증 벡터 `b"123456789"` → `0x29B1`.
- 프레임 = `COBS(논리패킷) + 0x00`.
- 테스트는 실제 시간에 의존하는 sleep 최소화(≤0.3s), 시리얼 하드웨어 불필요.
- 커밋 메시지: 한국어 conventional commit (`feat(server): ...`), 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: 프로젝트 스캐폴드 (uv + pyproject + 디렉토리)

**Files:**
- Create: `server/pyproject.toml`, `server/.gitignore`, `server/app/__init__.py`, `server/app/protocol/__init__.py`, `server/app/bridge/__init__.py`, `server/app/core/__init__.py`, `server/app/api/__init__.py`, `server/sim/__init__.py`, `server/tests/__init__.py`

**Interfaces:**
- Produces: `uv run pytest`가 동작하는 패키지 레이아웃. 이후 모든 태스크는 `from app.…` 절대 임포트 사용.

- [ ] **Step 1: 디렉토리·파일 생성**

```bash
cd ~/e-fairboard-project && mkdir -p server/app/{protocol,bridge,core,api} server/sim server/tests
touch server/app/__init__.py server/app/protocol/__init__.py server/app/bridge/__init__.py \
      server/app/core/__init__.py server/app/api/__init__.py server/sim/__init__.py server/tests/__init__.py
```

- [ ] **Step 2: pyproject.toml 작성**

`server/pyproject.toml`:
```toml
[project]
name = "efairboard-server"
version = "0.1.0"
description = "E-FairBoard 중앙 관리 서버 (FastAPI + 시리얼 브리지)"
requires-python = ">=3.12"
dependencies = [
    "fastapi[standard]>=0.115",
    "pyserial>=3.5",
    "apscheduler>=3.10",
]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["."]
testpaths = ["tests"]
```

`server/.gitignore`:
```
__pycache__/
.venv/
data/
*.tmp
```

- [ ] **Step 3: 의존성 설치·검증**

Run: `cd ~/e-fairboard-project/server && uv sync && uv run python -c "import fastapi, serial, apscheduler; print('ok')"`
Expected: `ok`

- [ ] **Step 4: pytest 동작 확인**

Run: `uv run pytest`
Expected: `no tests ran` (exit code 5 허용 — 테스트 0개)

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "chore(server): uv 프로젝트 스캐폴드

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: protocol/const.py + CRC16

**Files:**
- Create: `server/app/protocol/const.py`, `server/app/protocol/packet.py`(CRC만)
- Test: `server/tests/test_crc.py`

**Interfaces:**
- Produces: `MsgType`(IntEnum, PING=0x01…STATUS_RES=0x31), `AckResult`(OK=0…BAD_TYPE=3), `VER_V1=0x01`, `GATEWAY_ID=0x00`, `BROADCAST_ID=0xFF`, `crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int`

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_crc.py`:
```python
from app.protocol.packet import crc16_ccitt


def test_crc16_ccitt_false_표준벡터():
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_crc16_빈입력은_init값():
    assert crc16_ccitt(b"") == 0xFFFF


def test_crc16_한바이트_변조시_달라짐():
    assert crc16_ccitt(b"\x01\x02\x03") != crc16_ccitt(b"\x01\x02\x02")
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_crc.py -v`
Expected: FAIL — `ModuleNotFoundError` 또는 `ImportError`

- [ ] **Step 3: 구현**

`server/app/protocol/const.py`:
```python
"""PROTOCOL.md §3 상수. 펌웨어(gateway/node)와 값 동기화 필수."""
from enum import IntEnum

VER_V1 = 0x01
GATEWAY_ID = 0x00
BROADCAST_ID = 0xFF


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
```

`server/app/protocol/packet.py`:
```python
"""논리 패킷 코덱 (PROTOCOL.md §2). 순수 함수 — 시리얼·asyncio 무관."""


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflect, xorout 0."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_crc.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): 프로토콜 상수 + CRC-16/CCITT-FALSE

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Packet encode/decode

**Files:**
- Modify: `server/app/protocol/packet.py`
- Test: `server/tests/test_packet.py`

**Interfaces:**
- Consumes: `crc16_ccitt`, `VER_V1`
- Produces: `Packet(src, dst, type, seq, frag=0x80, payload=b"", ver=VER_V1)` frozen dataclass, `Packet.encode() -> bytes`, `decode(raw: bytes) -> Packet`, `PacketError(ValueError)`, `MAX_PAYLOAD=200`, `HEADER_LEN=7`
- 참고: PROTOCOL §2의 "8B 헤더" 표기는 필드 합(7B)과 불일치 — **필드 표 기준(7B 헤더 + 2B CRC = 9B)**으로 구현하고 Task 13에서 정정 TODO 기록.

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_packet.py`:
```python
import pytest

from app.protocol.const import MsgType
from app.protocol.packet import MAX_PAYLOAD, Packet, PacketError, decode


def test_빈_페이로드_인코딩은_9바이트():
    pkt = Packet(src=0x00, dst=0x01, type=MsgType.PING, seq=0)
    raw = pkt.encode()
    assert len(raw) == 9
    assert raw[:7] == bytes([0x01, 0x00, 0x01, 0x01, 0x00, 0x80, 0x00])


def test_encode_decode_왕복():
    pkt = Packet(src=0x00, dst=0x02, type=MsgType.SET_FIELD, seq=0x7F,
                 payload=bytes([0, 5]) + "제목".encode())
    assert decode(pkt.encode()) == pkt


def test_최대_페이로드_200B_왕복과_초과_거부():
    ok = Packet(src=0, dst=1, type=MsgType.SET_FIELD, seq=1, payload=b"x" * MAX_PAYLOAD)
    assert decode(ok.encode()).payload == b"x" * MAX_PAYLOAD
    with pytest.raises(PacketError):
        Packet(src=0, dst=1, type=MsgType.SET_FIELD, seq=1,
               payload=b"x" * (MAX_PAYLOAD + 1)).encode()


def test_CRC_오염시_PacketError():
    raw = bytearray(Packet(src=0, dst=1, type=MsgType.PING, seq=3).encode())
    raw[-1] ^= 0xFF
    with pytest.raises(PacketError, match="CRC"):
        decode(bytes(raw))


def test_LEN_불일치_및_짧은_프레임_거부():
    with pytest.raises(PacketError):
        decode(b"\x01\x00\x01")
    raw = bytearray(Packet(src=0, dst=1, type=MsgType.PING, seq=0).encode())
    raw[6] = 5  # LEN 조작
    with pytest.raises(PacketError):
        decode(bytes(raw))


def test_지원하지_않는_VER_거부():
    raw = bytearray(Packet(src=0, dst=1, type=MsgType.PING, seq=0).encode())
    raw[0] = 0x02
    with pytest.raises(PacketError, match="VER"):
        decode(bytes(raw))
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_packet.py -v`
Expected: FAIL — `ImportError: cannot import name 'Packet'`

- [ ] **Step 3: 구현 (packet.py에 추가)**

`server/app/protocol/packet.py` — 기존 `crc16_ccitt` 아래에 추가:
```python
from __future__ import annotations   # 파일 최상단으로

import struct
from dataclasses import dataclass

from app.protocol.const import VER_V1

HEADER_LEN = 7   # VER SRC DST TYPE SEQ FRAG LEN (PROTOCOL §2 필드 표 기준)
CRC_LEN = 2      # CRC16 little-endian
MAX_PAYLOAD = 200


class PacketError(ValueError):
    """프레임 디코딩 실패 (길이·버전·CRC 불일치)."""


@dataclass(frozen=True)
class Packet:
    src: int
    dst: int
    type: int
    seq: int
    frag: int = 0x80          # bit7=LAST, 단일 패킷 = 0x80
    payload: bytes = b""
    ver: int = VER_V1

    def encode(self) -> bytes:
        if len(self.payload) > MAX_PAYLOAD:
            raise PacketError(f"payload {len(self.payload)}B > {MAX_PAYLOAD}B")
        body = bytes([self.ver, self.src, self.dst, self.type,
                      self.seq, self.frag, len(self.payload)]) + self.payload
        return body + struct.pack("<H", crc16_ccitt(body))


def decode(raw: bytes) -> Packet:
    if len(raw) < HEADER_LEN + CRC_LEN:
        raise PacketError(f"frame too short: {len(raw)}B")
    ver, src, dst, typ, seq, frag, length = raw[:HEADER_LEN]
    if ver != VER_V1:
        raise PacketError(f"unsupported VER 0x{ver:02X}")
    if len(raw) != HEADER_LEN + length + CRC_LEN:
        raise PacketError(f"LEN mismatch: LEN={length}, frame={len(raw)}B")
    body = raw[:HEADER_LEN + length]
    (crc,) = struct.unpack("<H", raw[HEADER_LEN + length:])
    if crc != crc16_ccitt(body):
        raise PacketError("CRC mismatch")
    return Packet(src=src, dst=dst, type=typ, seq=seq, frag=frag,
                  payload=bytes(raw[HEADER_LEN:HEADER_LEN + length]), ver=ver)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_packet.py tests/test_crc.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): 논리 패킷 encode/decode (7B 헤더 + CRC16 LE)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: COBS 인코딩

**Files:**
- Create: `server/app/protocol/cobs.py`
- Test: `server/tests/test_cobs.py`

**Interfaces:**
- Produces: `encode(data: bytes) -> bytes`(0x00 미포함 결과), `decode(data: bytes) -> bytes`, `CobsError(ValueError)`

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_cobs.py`:
```python
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


def test_긴_데이터_왕복(길이_254_255_경계_포함=True):
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
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_cobs.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`server/app/protocol/cobs.py`:
```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_cobs.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): COBS 인코더/디코더

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Transport 추상 + SerialTransport + 테스트용 MemoryTransport

**Files:**
- Create: `server/app/bridge/transport.py`, `server/tests/conftest.py`
- Test: `server/tests/test_transport.py`

**Interfaces:**
- Produces: `Transport` ABC — `async open()`, `async close()`, `async read() -> bytes`(≥1바이트, 데이터까지 대기), `async write(data: bytes)`. `SerialTransport(port, baud=921600)`(실물용, 유닛테스트 제외). 테스트 전용 `MemoryTransport`(conftest) — `feed(data)`로 수신 주입, `.tx`로 송신 검사.

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/conftest.py`:
```python
import asyncio

from app.bridge.transport import Transport


class MemoryTransport(Transport):
    """테스트 더블: write는 tx에 축적, feed()로 read 큐에 주입."""

    def __init__(self):
        self.tx = bytearray()
        self._rx: asyncio.Queue[bytes] = asyncio.Queue()
        self.opened = False

    async def open(self):
        self.opened = True

    async def close(self):
        self.opened = False

    async def read(self) -> bytes:
        return await self._rx.get()

    async def write(self, data: bytes):
        self.tx += data

    def feed(self, data: bytes):
        self._rx.put_nowait(data)
```

`server/tests/test_transport.py`:
```python
import asyncio

from tests.conftest import MemoryTransport


async def test_memory_transport_왕복():
    t = MemoryTransport()
    await t.open()
    assert t.opened
    await t.write(b"abc")
    assert bytes(t.tx) == b"abc"
    t.feed(b"xyz")
    assert await t.read() == b"xyz"
    await t.close()
    assert not t.opened


async def test_read는_데이터까지_대기():
    t = MemoryTransport()
    task = asyncio.create_task(t.read())
    await asyncio.sleep(0.01)
    assert not task.done()
    t.feed(b"\x01")
    assert await task == b"\x01"


def test_serial_transport_임포트만_검증():
    from app.bridge.transport import SerialTransport
    st = SerialTransport("/dev/null-포트", baud=921600)
    assert st._port == "/dev/null-포트"   # 실물 연동은 하드웨어 도착 후 통합 검증
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_transport.py -v`
Expected: FAIL — `ModuleNotFoundError: app.bridge.transport`

- [ ] **Step 3: 구현**

`server/app/bridge/transport.py`:
```python
"""바이트 스트림 전송 계층. FakeGatewayTransport(sim/)와 SerialTransport의 교체점."""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import serial


class Transport(ABC):
    @abstractmethod
    async def open(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def read(self) -> bytes:
        """최소 1바이트를 데이터가 올 때까지 대기 후 반환."""

    @abstractmethod
    async def write(self, data: bytes) -> None: ...


class SerialTransport(Transport):
    """실물 게이트웨이용 pyserial 어댑터.

    블로킹 I/O를 executor로 감싼 최소 구현 — 유닛테스트 없음,
    실물(ESP32 게이트웨이) 도착 시 통합 검증.
    """

    def __init__(self, port: str, baud: int = 921600):
        self._port = port
        self._baud = baud
        self._ser: serial.Serial | None = None

    async def open(self) -> None:
        loop = asyncio.get_running_loop()
        self._ser = await loop.run_in_executor(
            None, lambda: serial.Serial(self._port, self._baud, timeout=0.2))

    async def close(self) -> None:
        if self._ser is not None:
            ser, self._ser = self._ser, None
            await asyncio.get_running_loop().run_in_executor(None, ser.close)

    async def read(self) -> bytes:
        return await asyncio.get_running_loop().run_in_executor(None, self._read_blocking)

    def _read_blocking(self) -> bytes:
        data = self._ser.read(1)             # timeout=0.2s 블로킹
        if data and self._ser.in_waiting:
            data += self._ser.read(self._ser.in_waiting)
        return data

    async def write(self, data: bytes) -> None:
        await asyncio.get_running_loop().run_in_executor(None, self._ser.write, data)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_transport.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): Transport 추상 계층 + SerialTransport + 테스트 더블

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: GatewayLink (프레이밍·SEQ·응답 매칭)

**Files:**
- Create: `server/app/bridge/gateway_link.py`
- Test: `server/tests/test_gateway_link.py`

**Interfaces:**
- Consumes: `Transport`, `MemoryTransport`, `cobs`, `Packet/decode/PacketError`, `MsgType`
- Produces: `GatewayLink(transport, *, timeout=6.0, on_event=None)` — `next_seq(dst) -> int`(노드별 0xFF→0x00 롤오버), `async start()`, `async stop()`, `async send(pkt)`, `async request(pkt, expect: MsgType, timeout=None) -> Packet`, `LinkTimeout(TimeoutError)`, `rx_dropped: int`
- 매칭 규칙: pending 키 = `(pkt.dst, expect)`. expect가 ACK이면 응답 `payload[0] == 보낸 seq`까지 일치해야 resolve(늦은 ACK 무시). 미매칭 수신 패킷은 `on_event(pkt)` 콜백.

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_gateway_link.py`:
```python
import asyncio

import pytest

from app.bridge.gateway_link import GatewayLink, LinkTimeout
from app.protocol import cobs
from app.protocol.const import GATEWAY_ID, MsgType
from app.protocol.packet import Packet
from tests.conftest import MemoryTransport


def frame(pkt: Packet) -> bytes:
    return cobs.encode(pkt.encode()) + b"\x00"


def ack_for(pkt: Packet, result: int = 0) -> Packet:
    return Packet(src=pkt.dst, dst=GATEWAY_ID, type=MsgType.ACK, seq=pkt.seq,
                  payload=bytes([pkt.seq, result]))


async def make_link(**kw):
    t = MemoryTransport()
    link = GatewayLink(t, timeout=0.2, **kw)
    await link.start()
    return t, link


async def test_request가_매칭되는_ACK를_반환():
    t, link = await make_link()
    pkt = Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.SET_TEMPLATE,
                 seq=link.next_seq(0x01), payload=b"\x00")
    asyncio.get_running_loop().call_later(0.02, t.feed, frame(ack_for(pkt)))
    resp = await link.request(pkt, MsgType.ACK)
    assert resp.payload[0] == pkt.seq
    assert bytes(t.tx) == frame(pkt)   # 송신 프레임 = COBS+0x00
    await link.stop()


async def test_다른_seq의_늦은_ACK는_무시하고_타임아웃():
    t, link = await make_link()
    pkt = Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.COMMIT,
                 seq=link.next_seq(0x01), payload=b"\x00")
    stale = Packet(src=0x01, dst=GATEWAY_ID, type=MsgType.ACK, seq=99,
                   payload=bytes([99, 0]))
    asyncio.get_running_loop().call_later(0.02, t.feed, frame(stale))
    with pytest.raises(LinkTimeout):
        await link.request(pkt, MsgType.ACK)
    await link.stop()


async def test_쓰레기_프레임은_폐기하고_다음_프레임은_정상처리():
    t, link = await make_link()
    pkt = Packet(src=GATEWAY_ID, dst=0x02, type=MsgType.PING, seq=link.next_seq(0x02))
    pong = Packet(src=0x02, dst=GATEWAY_ID, type=MsgType.PONG, seq=pkt.seq,
                  payload=b"\x3c\x0f\xc4\x00")
    asyncio.get_running_loop().call_later(
        0.02, t.feed, b"\x07garbage\x00" + frame(pong))
    resp = await link.request(pkt, MsgType.PONG)
    assert resp.type == MsgType.PONG
    assert link.rx_dropped == 1
    await link.stop()


async def test_seq는_노드별로_증가하고_0xFF에서_롤오버():
    _, link = await make_link()
    assert link.next_seq(0x01) == 0
    assert link.next_seq(0x01) == 1
    assert link.next_seq(0x02) == 0        # 노드별 독립
    link._seq[0x03] = 0xFE
    assert link.next_seq(0x03) == 0xFF
    assert link.next_seq(0x03) == 0x00     # 롤오버
    await link.stop()


async def test_비요청_패킷은_on_event_콜백으로():
    events = []
    t, link = await make_link(on_event=events.append)
    pong = Packet(src=0x01, dst=GATEWAY_ID, type=MsgType.PONG, seq=7,
                  payload=b"\x3c\x0f\xc4\x00")
    t.feed(frame(pong))
    await asyncio.sleep(0.05)
    assert events and events[0].type == MsgType.PONG
    await link.stop()


async def test_한_read청크에_여러_프레임():
    events = []
    t, link = await make_link(on_event=events.append)
    p1 = Packet(src=0x01, dst=GATEWAY_ID, type=MsgType.PONG, seq=1, payload=b"\x00\x00\x00\x00")
    p2 = Packet(src=0x02, dst=GATEWAY_ID, type=MsgType.PONG, seq=2, payload=b"\x00\x00\x00\x00")
    t.feed(frame(p1) + frame(p2))
    await asyncio.sleep(0.05)
    assert [e.src for e in events] == [0x01, 0x02]
    await link.stop()
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_gateway_link.py -v`
Expected: FAIL — `ModuleNotFoundError: app.bridge.gateway_link`

- [ ] **Step 3: 구현**

`server/app/bridge/gateway_link.py`:
```python
"""서버↔게이트웨이 링크: COBS 프레이밍, 노드별 SEQ, 요청-응답 매칭 (PROTOCOL §5·7)."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Callable

from app.bridge.transport import Transport
from app.protocol import cobs
from app.protocol.const import MsgType
from app.protocol.packet import Packet, PacketError, decode

log = logging.getLogger(__name__)
FRAME_DELIM = b"\x00"


class LinkTimeout(TimeoutError):
    """응답 타임아웃 — 상위(deploy)에서 재시도·OFFLINE 판단."""


class GatewayLink:
    def __init__(self, transport: Transport, *, timeout: float = 6.0,
                 on_event: Callable[[Packet], None] | None = None):
        self._t = transport
        self._timeout = timeout
        self._on_event = on_event
        self._seq: dict[int, int] = defaultdict(lambda: -1)
        # (src_node, expect_type) -> (expected_ack_seq | None, Future)
        self._pending: dict[tuple[int, int], tuple[int | None, asyncio.Future]] = {}
        self._buf = bytearray()
        self._reader: asyncio.Task | None = None
        self.rx_dropped = 0

    def next_seq(self, dst: int) -> int:
        self._seq[dst] = (self._seq[dst] + 1) & 0xFF
        return self._seq[dst]

    async def start(self) -> None:
        await self._t.open()
        self._reader = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
            self._reader = None
        await self._t.close()

    async def send(self, pkt: Packet) -> None:
        await self._t.write(cobs.encode(pkt.encode()) + FRAME_DELIM)

    async def request(self, pkt: Packet, expect: MsgType,
                      timeout: float | None = None) -> Packet:
        key = (pkt.dst, int(expect))
        exp_seq = pkt.seq if expect is MsgType.ACK else None
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[key] = (exp_seq, fut)
        try:
            await self.send(pkt)
            return await asyncio.wait_for(fut, timeout or self._timeout)
        except asyncio.TimeoutError:
            raise LinkTimeout(
                f"node 0x{pkt.dst:02X} {expect.name} 응답 없음") from None
        finally:
            self._pending.pop(key, None)

    async def _read_loop(self) -> None:
        backoff = 1.0
        while True:
            try:
                chunk = await self._t.read()
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as e:                    # 시리얼 단절 등
                log.warning("transport read 실패, %.0fs 후 재연결: %s", backoff, e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                try:
                    await self._t.close()
                    await self._t.open()
                except Exception as e2:
                    log.warning("재연결 실패: %s", e2)
                continue
            if not chunk:
                continue
            self._buf += chunk
            while (i := self._buf.find(0)) != -1:
                raw = bytes(self._buf[:i])
                del self._buf[:i + 1]
                if not raw:
                    continue
                try:
                    pkt = decode(cobs.decode(raw))
                except (PacketError, cobs.CobsError) as e:
                    self.rx_dropped += 1
                    log.warning("프레임 폐기(%d): %s", self.rx_dropped, e)
                    continue
                self._dispatch(pkt)

    def _dispatch(self, pkt: Packet) -> None:
        entry = self._pending.get((pkt.src, pkt.type))
        if entry:
            exp_seq, fut = entry
            matched = exp_seq is None or (pkt.payload and pkt.payload[0] == exp_seq)
            if matched and not fut.done():
                fut.set_result(pkt)
                return
        if self._on_event:
            self._on_event(pkt)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_gateway_link.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): GatewayLink — COBS 프레이밍·노드별 SEQ·요청-응답 매칭

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: core/templates.py (템플릿 4종 + 필드 검증)

**Files:**
- Create: `server/app/core/templates.py`
- Test: `server/tests/test_templates.py`

**Interfaces:**
- Produces: `FieldDef(field_id, label, max_len)`, `TemplateDef(template_id, name, fields, qr_slots=1)`, `TEMPLATES: dict[int, TemplateDef]`(PROTOCOL §8의 4종), `validate_fields(template_id, fields: dict[int, str]) -> None`(위반 시 `ValueError`), `MAX_TEXT_BYTES = 198`
- max_len 값은 서버 기준 잠정치 — 효민의 e-Paper 렌더 실측 후 동기화(스펙 §8.3).

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_templates.py`:
```python
import pytest

from app.core.templates import MAX_TEXT_BYTES, TEMPLATES, validate_fields


def test_템플릿_4종_정의():
    assert sorted(TEMPLATES) == [0, 1, 2, 3]
    assert TEMPLATES[0].name == "행사 안내"
    assert [f.field_id for f in TEMPLATES[0].fields] == [0, 1, 2, 3]


def test_정상_필드_통과():
    validate_fields(0, {0: "AI 경진대회", 1: "7/20 14:00", 2: "본관 101호"})


def test_없는_템플릿_거부():
    with pytest.raises(ValueError, match="템플릿"):
        validate_fields(9, {0: "x"})


def test_없는_필드id_거부():
    with pytest.raises(ValueError, match="필드"):
        validate_fields(1, {5: "x"})


def test_글자수_초과_거부():
    max_len = TEMPLATES[0].fields[0].max_len
    with pytest.raises(ValueError, match="초과"):
        validate_fields(0, {0: "가" * (max_len + 1)})


def test_UTF8_바이트_한도(monkeypatch):
    # 한글은 3B/자 — 글자수 제한과 별개로 198B 한도 검증
    from app.core import templates
    monkeypatch.setattr(
        templates, "TEMPLATES",
        {0: templates.TemplateDef(0, "테스트",
            (templates.FieldDef(0, "긴필드", 100),))})
    with pytest.raises(ValueError, match=str(MAX_TEXT_BYTES)):
        templates.validate_fields(0, {0: "가" * 70})   # 210B > 198B
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_templates.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`server/app/core/templates.py`:
```python
"""노드 템플릿 정의 (PROTOCOL §8). 좌표·폰트는 펌웨어 상수, 서버는 값만 검증·전송.

max_len은 서버 잠정치 — e-Paper 렌더 실측 후 펌웨어와 동기화할 것.
"""
from dataclasses import dataclass

MAX_TEXT_BYTES = 198   # SET_FIELD payload 한도: 200 - field_id(1) - text_len(1)


@dataclass(frozen=True)
class FieldDef:
    field_id: int
    label: str
    max_len: int   # 글자 수


@dataclass(frozen=True)
class TemplateDef:
    template_id: int
    name: str
    fields: tuple[FieldDef, ...]
    qr_slots: int = 1


TEMPLATES: dict[int, TemplateDef] = {
    0: TemplateDef(0, "행사 안내", (
        FieldDef(0, "제목", 32), FieldDef(1, "일시", 24),
        FieldDef(2, "장소", 24), FieldDef(3, "비고", 40))),
    1: TemplateDef(1, "부스 지도", (
        FieldDef(0, "구역명", 16), FieldDef(1, "부스번호", 8))),
    2: TemplateDef(2, "모집 공고", (
        FieldDef(0, "제목", 32), FieldDef(1, "마감", 24), FieldDef(2, "대상", 24))),
    3: TemplateDef(3, "일정표", (
        FieldDef(0, "날짜", 16), FieldDef(1, "세션1", 32),
        FieldDef(2, "세션2", 32), FieldDef(3, "세션3", 32))),
}


def validate_fields(template_id: int, fields: dict[int, str]) -> None:
    tpl = TEMPLATES.get(template_id)
    if tpl is None:
        raise ValueError(f"알 수 없는 템플릿 {template_id}")
    defs = {f.field_id: f for f in tpl.fields}
    for fid, text in fields.items():
        f = defs.get(fid)
        if f is None:
            raise ValueError(f"템플릿 {template_id}에 없는 필드 {fid}")
        if len(text) > f.max_len:
            raise ValueError(f"{f.label}: {f.max_len}자 초과")
        if len(text.encode()) > MAX_TEXT_BYTES:
            raise ValueError(f"{f.label}: {MAX_TEXT_BYTES}B 초과")
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_templates.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): 템플릿 4종 정의 + 필드 검증

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: core/state.py (Node·Post·Stats + JSON 영속)

**Files:**
- Create: `server/app/core/state.py`
- Test: `server/tests/test_state.py`

**Interfaces:**
- Produces:
  - `Node(node_id, name, online=False, last_seen=None, batt_mv=None, rssi=None, err_cnt=0, template_id=None)`
  - `Post(id, template_id, fields={}, qr_url=None, target_node_ids=[], status="draft", schedule_at=None, deployed_at=None)` — status ∈ draft|scheduled|deploying|deployed|partial|failed, schedule_at/deployed_at는 ISO8601 문자열
  - `Stats(deploy_success=0, deploy_fail=0, paper_saved=0)`
  - `StateStore(path)` — `.nodes: dict[int, Node]`, `.posts: dict[str, Post]`, `.stats: Stats`, `.save()`(tmp+os.replace 원자적), `.new_post(template_id, fields, qr_url, target_node_ids) -> Post`
  - 파일 없으면 기본 노드 2대(0x01 "노드1", 0x02 "노드2") 생성.

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_state.py`:
```python
import json

from app.core.state import Node, Post, StateStore


def test_파일_없으면_기본_노드_2대(tmp_path):
    store = StateStore(tmp_path / "state.json")
    assert sorted(store.nodes) == [0x01, 0x02]
    assert store.nodes[0x01].name == "노드1"
    assert store.stats.deploy_success == 0


def test_저장_후_재로드_왕복(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    post = store.new_post(template_id=0, fields={0: "제목", 1: "7/20"},
                          qr_url="https://ex.am/1", target_node_ids=[1, 2])
    store.nodes[0x01].batt_mv = 3812
    store.stats.paper_saved = 5
    store.save()

    re = StateStore(path)
    assert re.posts[post.id].fields == {0: "제목", 1: "7/20"}   # int 키 보존
    assert re.posts[post.id].qr_url == "https://ex.am/1"
    assert re.nodes[0x01].batt_mv == 3812
    assert re.stats.paper_saved == 5


def test_new_post는_id를_발급하고_즉시_영속(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    post = store.new_post(0, {}, None, [])
    assert len(post.id) == 8
    assert post.status == "draft"
    assert post.id in json.loads(path.read_text())["posts"]


def test_원자적_쓰기_tmp파일_잔존_없음(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.save()
    assert path.exists()
    assert not path.with_suffix(".tmp").exists()
    json.loads(path.read_text())   # 항상 유효한 JSON
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`server/app/core/state.py`:
```python
"""인메모리 상태 + JSON 영속 (ARCHITECTURE §6: MVP는 DB 없음)."""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Node:
    node_id: int
    name: str
    online: bool = False
    last_seen: float | None = None     # epoch 초
    batt_mv: int | None = None
    rssi: int | None = None
    err_cnt: int = 0
    template_id: int | None = None     # 마지막 COMMIT 성공 템플릿


@dataclass
class Post:
    id: str
    template_id: int
    fields: dict[int, str] = field(default_factory=dict)
    qr_url: str | None = None
    target_node_ids: list[int] = field(default_factory=list)
    status: str = "draft"   # draft|scheduled|deploying|deployed|partial|failed
    schedule_at: str | None = None     # ISO8601
    deployed_at: str | None = None


@dataclass
class Stats:
    deploy_success: int = 0
    deploy_fail: int = 0
    paper_saved: int = 0


DEFAULT_NODES = {0x01: "노드1", 0x02: "노드2"}


class StateStore:
    def __init__(self, path: Path | str):
        self._path = Path(path)
        self.nodes: dict[int, Node] = {}
        self.posts: dict[str, Post] = {}
        self.stats = Stats()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self.nodes = {nid: Node(nid, name) for nid, name in DEFAULT_NODES.items()}
            return
        raw = json.loads(self._path.read_text())
        self.nodes = {int(k): Node(**v) for k, v in raw["nodes"].items()}
        self.posts = {
            k: Post(**{**v, "fields": {int(fk): fv for fk, fv in v["fields"].items()}})
            for k, v in raw["posts"].items()}
        self.stats = Stats(**raw["stats"])

    def save(self) -> None:
        raw = {
            "nodes": {str(k): asdict(v) for k, v in self.nodes.items()},
            "posts": {k: asdict(v) for k, v in self.posts.items()},
            "stats": asdict(self.stats),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=1))
        os.replace(tmp, self._path)   # 원자적 교체

    def new_post(self, template_id: int, fields: dict[int, str],
                 qr_url: str | None, target_node_ids: list[int]) -> Post:
        post = Post(id=uuid.uuid4().hex[:8], template_id=template_id,
                    fields=dict(fields), qr_url=qr_url,
                    target_node_ids=list(target_node_ids))
        self.posts[post.id] = post
        self.save()
        return post
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_state.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): StateStore — 메모리 상태 + JSON 원자적 영속

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: sim/fake_gateway.py (모의 게이트웨이 + 가상 노드)

**Files:**
- Create: `server/sim/fake_gateway.py`
- Test: `server/tests/test_fake_gateway.py`

**Interfaces:**
- Consumes: `Transport`, `cobs`, `Packet/decode`, `MsgType`, `AckResult`, `GATEWAY_ID`, `BROADCAST_ID`
- Produces:
  - `VirtualNode(node_id, batt_mv=3900, rssi=-60)` — `.handle(pkt) -> Packet | None`, `.silent: bool`(실패 주입), `.staging/.committed: dict[int, str]`, `.qr: dict[int, str]`, `.template_id`, `.last_refresh: int | None`, (TYPE,SEQ) 중복 시 동일 ACK 재전송(멱등)
  - `FakeGatewayTransport(nodes=None, *, slot_ms=0, latency=0.0)` — 기본 노드 0x01·0x02. `write()`가 프레임을 디코드해 노드로 라우팅, 응답을 read 큐로. 브로드캐스트는 `NodeID×slot_ms` 지연 ACK(PROTOCOL §5).
- ACK payload = `bytes([ack_seq, result])`. PONG payload = `struct.pack("<Hb", batt_mv, rssi) + bytes([status])`. STATUS_RES payload = `struct.pack("<HBHB", batt_mv, last_seq, uptime_s, err_cnt)` — 모두 little-endian.

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_fake_gateway.py`:
```python
import asyncio
import struct

import pytest

from app.protocol import cobs
from app.protocol.const import BROADCAST_ID, GATEWAY_ID, AckResult, MsgType
from app.protocol.packet import Packet, decode
from sim.fake_gateway import FakeGatewayTransport, VirtualNode


def frame(pkt: Packet) -> bytes:
    return cobs.encode(pkt.encode()) + b"\x00"


async def roundtrip(gw: FakeGatewayTransport, pkt: Packet) -> Packet:
    await gw.write(frame(pkt))
    raw = await asyncio.wait_for(gw.read(), 1.0)
    return decode(cobs.decode(raw.rstrip(b"\x00")))


async def test_PING에_PONG_응답():
    gw = FakeGatewayTransport()
    resp = await roundtrip(gw, Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.PING, seq=0))
    assert resp.type == MsgType.PONG and resp.src == 0x01
    batt, rssi = struct.unpack("<Hb", resp.payload[:3])
    assert batt == 3900 and rssi == -60


async def test_SET_FIELD와_COMMIT_흐름():
    gw = FakeGatewayTransport()
    node = gw.nodes[0x01]
    text = "행사안내".encode()
    r1 = await roundtrip(gw, Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.SET_FIELD,
                                    seq=1, payload=bytes([0, len(text)]) + text))
    assert r1.type == MsgType.ACK and r1.payload[1] == AckResult.OK
    assert node.staging == {0: "행사안내"} and node.committed == {}
    r2 = await roundtrip(gw, Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.COMMIT,
                                    seq=2, payload=b"\x01"))
    assert r2.payload[1] == AckResult.OK
    assert node.committed == {0: "행사안내"} and node.last_refresh == 1


async def test_중복_SEQ는_재적용_없이_동일_ACK():
    gw = FakeGatewayTransport()
    node = gw.nodes[0x02]
    pkt = Packet(src=GATEWAY_ID, dst=0x02, type=MsgType.SET_TEMPLATE, seq=5, payload=b"\x02")
    r1 = await roundtrip(gw, pkt)
    node.template_id = 99            # 재적용되면 다시 2로 덮일 것
    r2 = await roundtrip(gw, pkt)    # 같은 (TYPE,SEQ)
    assert r1 == r2
    assert node.template_id == 99    # 멱등: 재적용 안 됨


async def test_silent_노드는_무응답():
    gw = FakeGatewayTransport()
    gw.nodes[0x01].silent = True
    await gw.write(frame(Packet(src=GATEWAY_ID, dst=0x01, type=MsgType.PING, seq=0)))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(gw.read(), 0.1)


async def test_브로드캐스트는_노드별_슬롯지연_ACK():
    gw = FakeGatewayTransport(slot_ms=30)
    await gw.write(frame(Packet(src=GATEWAY_ID, dst=BROADCAST_ID,
                                type=MsgType.COMMIT, seq=9, payload=b"\x00")))
    srcs = []
    for _ in range(2):
        raw = await asyncio.wait_for(gw.read(), 1.0)
        srcs.append(decode(cobs.decode(raw.rstrip(b"\x00"))).src)
    assert srcs == [0x01, 0x02]      # NodeID×slot 순서


async def test_STATUS_REQ_응답_포맷():
    gw = FakeGatewayTransport()
    resp = await roundtrip(gw, Packet(src=GATEWAY_ID, dst=0x01,
                                      type=MsgType.STATUS_REQ, seq=3))
    assert resp.type == MsgType.STATUS_RES
    batt, last_seq, uptime, err = struct.unpack("<HBHB", resp.payload)
    assert batt == 3900 and err == 0
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_fake_gateway.py -v`
Expected: FAIL — `ModuleNotFoundError: sim.fake_gateway`

- [ ] **Step 3: 구현**

`server/sim/fake_gateway.py`:
```python
"""모의 게이트웨이: 실물 하드웨어 없이 서버 E2E 개발·시연용.

GW=투명 릴레이 가정(스펙 §8.1) — 서버 프레임을 가상 노드 상태머신에 전달하고
노드 응답을 그대로 프레이밍해 돌려준다. LoRa 전파·재전송은 모사하지 않는다.
"""
from __future__ import annotations

import asyncio
import struct
import time

from app.bridge.transport import Transport
from app.protocol import cobs
from app.protocol.const import BROADCAST_ID, GATEWAY_ID, AckResult, MsgType
from app.protocol.packet import Packet, decode


class VirtualNode:
    def __init__(self, node_id: int, batt_mv: int = 3900, rssi: int = -60):
        self.node_id = node_id
        self.batt_mv = batt_mv
        self.rssi = rssi
        self.template_id: int | None = None
        self.staging: dict[int, str] = {}
        self.committed: dict[int, str] = {}
        self.qr: dict[int, str] = {}
        self.last_refresh: int | None = None
        self.silent = False                     # 실패 주입: 무응답
        self.err_cnt = 0
        self._last: tuple[int, int] | None = None   # (TYPE, SEQ) 중복 검출
        self._last_resp: Packet | None = None
        self._boot = time.monotonic()

    def handle(self, pkt: Packet) -> Packet | None:
        if self.silent:
            return None
        if self._last == (pkt.type, pkt.seq) and self._last_resp is not None:
            return self._last_resp              # 멱등: 재적용 없이 응답만 재전송
        resp = self._process(pkt)
        self._last = (pkt.type, pkt.seq)
        self._last_resp = resp
        return resp

    def _ack(self, pkt: Packet, result: AckResult = AckResult.OK) -> Packet:
        return Packet(src=self.node_id, dst=GATEWAY_ID, type=MsgType.ACK,
                      seq=pkt.seq, payload=bytes([pkt.seq, result]))

    def _process(self, pkt: Packet) -> Packet:
        t = pkt.type
        if t == MsgType.PING:
            return Packet(src=self.node_id, dst=GATEWAY_ID, type=MsgType.PONG,
                          seq=pkt.seq,
                          payload=struct.pack("<Hb", self.batt_mv, self.rssi) + b"\x00")
        if t == MsgType.SET_TEMPLATE:
            self.template_id = pkt.payload[0]
            self.staging.clear()
            return self._ack(pkt)
        if t == MsgType.SET_FIELD:
            fid, ln = pkt.payload[0], pkt.payload[1]
            self.staging[fid] = pkt.payload[2:2 + ln].decode()
            return self._ack(pkt)
        if t == MsgType.SET_QR:
            slot, ln = pkt.payload[0], pkt.payload[1]
            self.qr[slot] = pkt.payload[2:2 + ln].decode()
            return self._ack(pkt)
        if t == MsgType.COMMIT:
            self.committed = dict(self.staging)
            self.last_refresh = pkt.payload[0]
            return self._ack(pkt)
        if t == MsgType.STATUS_REQ:
            uptime = int(time.monotonic() - self._boot) & 0xFFFF
            last_seq = self._last[1] if self._last else 0
            return Packet(src=self.node_id, dst=GATEWAY_ID, type=MsgType.STATUS_RES,
                          seq=pkt.seq,
                          payload=struct.pack("<HBHB", self.batt_mv, last_seq,
                                              uptime, self.err_cnt))
        self.err_cnt += 1
        return self._ack(pkt, AckResult.BAD_TYPE)


class FakeGatewayTransport(Transport):
    def __init__(self, nodes: dict[int, VirtualNode] | None = None, *,
                 slot_ms: int = 0, latency: float = 0.0):
        self.nodes = nodes if nodes is not None else {
            0x01: VirtualNode(0x01), 0x02: VirtualNode(0x02)}
        self._rx: asyncio.Queue[bytes] = asyncio.Queue()
        self._buf = bytearray()
        self._slot = slot_ms / 1000
        self._latency = latency

    async def open(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def read(self) -> bytes:
        return await self._rx.get()

    async def write(self, data: bytes) -> None:
        self._buf += data
        while (i := self._buf.find(0)) != -1:
            raw = bytes(self._buf[:i])
            del self._buf[:i + 1]
            if raw:
                self._route(decode(cobs.decode(raw)))

    def _route(self, pkt: Packet) -> None:
        if pkt.dst == BROADCAST_ID:
            targets = [self.nodes[k] for k in sorted(self.nodes)]
        else:
            node = self.nodes.get(pkt.dst)
            targets = [node] if node else []
        for node in targets:
            resp = node.handle(pkt)
            if resp is None:
                continue
            delay = self._latency
            if pkt.dst == BROADCAST_ID:
                delay += node.node_id * self._slot   # §5 ACK 슬롯
            payload = cobs.encode(resp.encode()) + b"\x00"
            if delay > 0:
                asyncio.get_running_loop().call_later(
                    delay, self._rx.put_nowait, payload)
            else:
                self._rx.put_nowait(payload)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_fake_gateway.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): 모의 게이트웨이 + 가상 노드 2대 (실패 주입·멱등·브로드캐스트 슬롯)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: core/deploy.py (배포 오케스트레이터)

**Files:**
- Create: `server/app/core/deploy.py`
- Test: `server/tests/test_deploy.py`

**Interfaces:**
- Consumes: `GatewayLink.request/next_seq`, `LinkTimeout`, `StateStore/Node/Post`, `MsgType/AckResult/GATEWAY_ID`, `Packet`
- Produces:
  - `DeployError(RuntimeError)`
  - `DeployResult` — `.ok_nodes: list[int]`, `.failed_nodes: list[int]`, `.status`(property: deployed|partial|failed)
  - `async deploy_post(link, store, post, node_ids=None) -> DeployResult` — §4 시퀀스(SET_TEMPLATE는 노드의 template_id와 다를 때만, refresh_mode=1) → 필드 fid 오름차순 SET_FIELD → qr_url 있으면 SET_QR(slot 0) → COMMIT. 패킷별 타임아웃 시 재시도 1회. 성공 노드: online=True·last_seen 갱신·stats.deploy_success+1·paper_saved+1. 실패 노드: online=False·err_cnt+1·stats.deploy_fail+1. post.status/deployed_at 갱신 후 `store.save()`.

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_deploy.py`:
```python
from app.bridge.gateway_link import GatewayLink
from app.core.deploy import deploy_post
from app.core.state import StateStore
from sim.fake_gateway import FakeGatewayTransport


async def make_env(tmp_path, **gw_kw):
    gw = FakeGatewayTransport(**gw_kw)
    link = GatewayLink(gw, timeout=0.3)
    await link.start()
    store = StateStore(tmp_path / "state.json")
    return gw, link, store


async def test_2노드_배포_성공(tmp_path):
    gw, link, store = await make_env(tmp_path)
    post = store.new_post(0, {0: "AI 경진대회", 1: "7/20 14:00"},
                          "https://ex.am/detail", [1, 2])
    result = await deploy_post(link, store, post)
    assert result.status == "deployed"
    assert result.ok_nodes == [1, 2] and not result.failed_nodes
    for nid in (1, 2):
        assert gw.nodes[nid].committed == {0: "AI 경진대회", 1: "7/20 14:00"}
        assert gw.nodes[nid].qr == {0: "https://ex.am/detail"}
        assert gw.nodes[nid].template_id == 0
        assert store.nodes[nid].online and store.nodes[nid].template_id == 0
    assert post.status == "deployed" and post.deployed_at
    assert store.stats.deploy_success == 2 and store.stats.paper_saved == 2
    await link.stop()


async def test_무응답_노드는_partial_및_offline(tmp_path):
    gw, link, store = await make_env(tmp_path)
    gw.nodes[0x02].silent = True
    post = store.new_post(0, {0: "제목"}, None, [1, 2])
    result = await deploy_post(link, store, post)
    assert result.status == "partial"
    assert result.ok_nodes == [1] and result.failed_nodes == [2]
    assert store.nodes[2].online is False and store.nodes[2].err_cnt == 1
    assert store.stats.deploy_fail == 1
    await link.stop()


async def test_전_노드_실패면_failed(tmp_path):
    gw, link, store = await make_env(tmp_path)
    gw.nodes[0x01].silent = True
    gw.nodes[0x02].silent = True
    post = store.new_post(0, {0: "제목"}, None, [1, 2])
    result = await deploy_post(link, store, post)
    assert result.status == "failed" and post.status == "failed"
    await link.stop()


async def test_같은_템플릿_재배포는_SET_TEMPLATE_생략_부분갱신(tmp_path):
    gw, link, store = await make_env(tmp_path)
    p1 = store.new_post(0, {0: "v1"}, None, [1])
    await deploy_post(link, store, p1)
    assert gw.nodes[1].last_refresh == 1        # 첫 배포: 전체갱신
    p2 = store.new_post(0, {0: "v2"}, None, [1])
    await deploy_post(link, store, p2)
    assert gw.nodes[1].last_refresh == 0        # 같은 템플릿: 부분갱신
    assert gw.nodes[1].committed == {0: "v2"}
    await link.stop()


async def test_node_ids_인자가_타깃_오버라이드(tmp_path):
    gw, link, store = await make_env(tmp_path)
    post = store.new_post(0, {0: "x"}, None, [1, 2])
    result = await deploy_post(link, store, post, node_ids=[1])
    assert result.ok_nodes == [1]
    assert gw.nodes[2].committed == {}
    await link.stop()
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_deploy.py -v`
Expected: FAIL — `ModuleNotFoundError: app.core.deploy`

- [ ] **Step 3: 구현**

`server/app/core/deploy.py`:
```python
"""게시물 배포 오케스트레이터 (PROTOCOL §4 시퀀스)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.bridge.gateway_link import GatewayLink, LinkTimeout
from app.core.state import Node, Post, StateStore
from app.protocol.const import GATEWAY_ID, AckResult, MsgType
from app.protocol.packet import Packet

log = logging.getLogger(__name__)
RETRIES = 1   # 서버 상위 재시도 — LoRa 구간 재전송(§5)은 GW 담당


class DeployError(RuntimeError):
    """ACK result != OK."""


@dataclass
class DeployResult:
    ok_nodes: list[int] = field(default_factory=list)
    failed_nodes: list[int] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.failed_nodes:
            return "deployed"
        if not self.ok_nodes:
            return "failed"
        return "partial"


async def _send_checked(link: GatewayLink, dst: int, type_: MsgType,
                        payload: bytes) -> None:
    """SEQ 발급→전송→ACK(result=OK) 확인. 타임아웃/오류 시 재시도 후 예외."""
    last_exc: Exception = LinkTimeout("unreachable")
    for _ in range(RETRIES + 1):
        pkt = Packet(src=GATEWAY_ID, dst=dst, type=type_,
                     seq=link.next_seq(dst), payload=payload)
        try:
            resp = await link.request(pkt, MsgType.ACK)
        except LinkTimeout as e:
            last_exc = e
            continue
        if len(resp.payload) >= 2 and resp.payload[1] == AckResult.OK:
            return
        last_exc = DeployError(
            f"{type_.name} ACK result={resp.payload[1] if len(resp.payload) > 1 else '?'}")
    raise last_exc


async def _deploy_node(link: GatewayLink, node: Node, post: Post) -> None:
    template_changed = node.template_id != post.template_id
    if template_changed:
        await _send_checked(link, node.node_id, MsgType.SET_TEMPLATE,
                            bytes([post.template_id]))
    for fid in sorted(post.fields):
        text = post.fields[fid].encode()
        await _send_checked(link, node.node_id, MsgType.SET_FIELD,
                            bytes([fid, len(text)]) + text)
    if post.qr_url:
        url = post.qr_url.encode()
        await _send_checked(link, node.node_id, MsgType.SET_QR,
                            bytes([0, len(url)]) + url)
    refresh = 1 if template_changed else 0   # 템플릿 전환=전체갱신(§4)
    await _send_checked(link, node.node_id, MsgType.COMMIT, bytes([refresh]))
    node.template_id = post.template_id


async def deploy_post(link: GatewayLink, store: StateStore, post: Post,
                      node_ids: list[int] | None = None) -> DeployResult:
    ids = node_ids or post.target_node_ids or sorted(store.nodes)
    post.status = "deploying"
    store.save()
    result = DeployResult()
    for nid in ids:
        node = store.nodes.get(nid)
        if node is None:
            log.warning("알 수 없는 노드 0x%02X — 건너뜀", nid)
            result.failed_nodes.append(nid)
            store.stats.deploy_fail += 1
            continue
        try:
            await _deploy_node(link, node, post)
        except (LinkTimeout, DeployError) as e:
            log.warning("노드 0x%02X 배포 실패: %s", nid, e)
            node.online = False
            node.err_cnt += 1
            result.failed_nodes.append(nid)
            store.stats.deploy_fail += 1
            continue
        node.online = True
        node.last_seen = time.time()
        result.ok_nodes.append(nid)
        store.stats.deploy_success += 1
        store.stats.paper_saved += 1
    post.status = result.status
    post.deployed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store.save()
    return result
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_deploy.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): 배포 오케스트레이터 — §4 시퀀스·재시도·OFFLINE·통계

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: core/scheduler.py (예약 배포)

**Files:**
- Create: `server/app/core/scheduler.py`
- Test: `server/tests/test_scheduler.py`

**Interfaces:**
- Consumes: `StateStore/Post`
- Produces: `DeployScheduler(deploy_cb)` — `deploy_cb: async (post_id: str) -> None`. `start(store)`(스케줄러 기동 + `scheduled` 포스트 재등록: 미래→job, 과거→status="failed"), `schedule(post_id, at: datetime)`, `cancel(post_id)`, `shutdown()`, `has_job(post_id) -> bool`

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_scheduler.py`:
```python
import asyncio
from datetime import datetime, timedelta, timezone

from app.core.scheduler import DeployScheduler
from app.core.state import StateStore


def utcnow():
    return datetime.now(timezone.utc)


async def test_예약시각에_콜백_실행(tmp_path):
    called = []

    async def cb(post_id):
        called.append(post_id)

    sched = DeployScheduler(cb)
    sched.start(StateStore(tmp_path / "s.json"))
    sched.schedule("abc123", utcnow() + timedelta(seconds=0.1))
    assert sched.has_job("abc123")
    await asyncio.sleep(0.3)
    assert called == ["abc123"]
    assert not sched.has_job("abc123")
    sched.shutdown()


async def test_취소하면_실행_안됨(tmp_path):
    called = []

    async def cb(post_id):
        called.append(post_id)

    sched = DeployScheduler(cb)
    sched.start(StateStore(tmp_path / "s.json"))
    sched.schedule("abc123", utcnow() + timedelta(seconds=0.1))
    sched.cancel("abc123")
    await asyncio.sleep(0.2)
    assert called == []
    sched.shutdown()


async def test_기동시_미래예약_재등록_과거예약은_failed(tmp_path):
    store = StateStore(tmp_path / "s.json")
    future = store.new_post(0, {}, None, [])
    future.status = "scheduled"
    future.schedule_at = (utcnow() + timedelta(hours=1)).isoformat()
    past = store.new_post(0, {}, None, [])
    past.status = "scheduled"
    past.schedule_at = (utcnow() - timedelta(hours=1)).isoformat()
    store.save()

    async def cb(post_id):
        pass

    sched = DeployScheduler(cb)
    sched.start(store)
    assert sched.has_job(future.id)
    assert not sched.has_job(past.id)
    assert store.posts[past.id].status == "failed"
    sched.shutdown()
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 구현**

`server/app/core/scheduler.py`:
```python
"""예약 배포 — APScheduler 인메모리 잡 + JSON 영속 포스트에서 기동 시 복원."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from app.core.state import StateStore

log = logging.getLogger(__name__)


class DeployScheduler:
    def __init__(self, deploy_cb: Callable[[str], Awaitable[None]]):
        self._sched = AsyncIOScheduler()
        self._cb = deploy_cb

    def start(self, store: StateStore) -> None:
        self._sched.start()
        now = datetime.now(timezone.utc)
        dirty = False
        for post in store.posts.values():
            if post.status != "scheduled" or not post.schedule_at:
                continue
            at = datetime.fromisoformat(post.schedule_at)
            if at > now:
                self.schedule(post.id, at)
                log.info("예약 복원: %s @ %s", post.id, post.schedule_at)
            else:
                post.status = "failed"   # 서버 다운 중 지나간 예약
                dirty = True
                log.warning("지난 예약 failed 처리: %s @ %s", post.id, post.schedule_at)
        if dirty:
            store.save()

    def schedule(self, post_id: str, at: datetime) -> None:
        self._sched.add_job(self._cb, DateTrigger(run_date=at),
                            args=[post_id], id=post_id, replace_existing=True)

    def cancel(self, post_id: str) -> None:
        if self._sched.get_job(post_id):
            self._sched.remove_job(post_id)

    def has_job(self, post_id: str) -> bool:
        return self._sched.get_job(post_id) is not None

    def shutdown(self) -> None:
        if self._sched.running:
            self._sched.shutdown(wait=False)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_scheduler.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): 예약 배포 스케줄러 — 기동 시 예약 복원

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: config + FastAPI 앱 + REST API

**Files:**
- Create: `server/app/config.py`, `server/app/main.py`, `server/app/api/templates.py`, `server/app/api/posts.py`, `server/app/api/deploy.py`, `server/app/api/nodes.py`, `server/app/api/stats.py`
- Test: `server/tests/test_api.py`

**Interfaces:**
- Consumes: 지금까지의 전 모듈
- Produces:
  - `app.main.app` (FastAPI) — lifespan에서 `StateStore`·`GatewayLink`(EFB_SERIAL_PORT 미설정 시 FakeGatewayTransport)·`DeployScheduler` 생성, `app.state.store/link/scheduler`에 보관. **config 값은 lifespan 시점에 읽는다**(테스트 monkeypatch 가능하도록).
  - 엔드포인트(스펙 §3.4 표): GET `/api/templates` · POST/GET `/api/posts` · GET/PUT/DELETE `/api/posts/{id}` · POST `/api/posts/{id}/deploy` · POST/DELETE `/api/posts/{id}/schedule` · GET `/api/nodes` · POST `/api/nodes/{id}/ping` · POST `/api/nodes/{id}/status` · GET `/api/stats` · GET `/api/health`
  - 비요청 수신 패킷(PONG 등)은 on_event로 노드 online/last_seen 갱신.

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_api.py`:
```python
from fastapi.testclient import TestClient

from app import config


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(config, "SERIAL_PORT", None)      # FakeGW 모드
    monkeypatch.setattr(config, "DATA_PATH", tmp_path / "state.json")
    monkeypatch.setattr(config, "LINK_TIMEOUT", 0.3)
    from app.main import app
    return TestClient(app)


def test_health_및_templates(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        assert c.get("/api/health").json()["ok"] is True
        tpls = c.get("/api/templates").json()
        assert len(tpls) == 4
        assert tpls[0]["name"] == "행사 안내"


def test_post_CRUD(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        r = c.post("/api/posts", json={
            "template_id": 0,
            "fields": {"0": "AI 경진대회", "1": "7/20 14:00"},
            "qr_url": "https://ex.am/1",
            "target_node_ids": [1, 2]})
        assert r.status_code == 201
        pid = r.json()["id"]
        assert c.get(f"/api/posts/{pid}").json()["fields"]["0"] == "AI 경진대회"
        r = c.put(f"/api/posts/{pid}", json={
            "template_id": 0, "fields": {"0": "수정됨"},
            "qr_url": None, "target_node_ids": [1]})
        assert r.json()["fields"]["0"] == "수정됨"
        assert c.delete(f"/api/posts/{pid}").status_code == 204
        assert c.get(f"/api/posts/{pid}").status_code == 404


def test_잘못된_필드는_422(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        r = c.post("/api/posts", json={
            "template_id": 0, "fields": {"9": "없는 필드"},
            "qr_url": None, "target_node_ids": []})
        assert r.status_code == 422


def test_배포_E2E_노드_online_및_통계(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        pid = c.post("/api/posts", json={
            "template_id": 0, "fields": {"0": "공지"},
            "qr_url": "https://ex.am/q", "target_node_ids": [1, 2]}).json()["id"]
        r = c.post(f"/api/posts/{pid}/deploy", json={})
        assert r.json() == {"status": "deployed", "ok_nodes": [1, 2], "failed_nodes": []}
        nodes = {n["node_id"]: n for n in c.get("/api/nodes").json()}
        assert nodes[1]["online"] and nodes[2]["online"]
        stats = c.get("/api/stats").json()
        assert stats["paper_saved"] == 2


def test_ping과_status(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        r = c.post("/api/nodes/1/ping")
        assert r.status_code == 200
        assert r.json()["batt_mv"] == 3900
        r = c.post("/api/nodes/1/status")
        assert r.json()["batt_mv"] == 3900
        r = c.post("/api/nodes/99/ping")
        assert r.status_code == 404


def test_예약_등록과_취소(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as c:
        pid = c.post("/api/posts", json={
            "template_id": 0, "fields": {"0": "예약"},
            "qr_url": None, "target_node_ids": [1]}).json()["id"]
        r = c.post(f"/api/posts/{pid}/schedule",
                   json={"at": "2099-01-01T00:00:00+00:00"})
        assert r.status_code == 200
        assert c.get(f"/api/posts/{pid}").json()["status"] == "scheduled"
        assert c.delete(f"/api/posts/{pid}/schedule").status_code == 200
        assert c.get(f"/api/posts/{pid}").json()["status"] == "draft"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: app.config`

- [ ] **Step 3: 구현**

`server/app/config.py`:
```python
"""환경설정. 값은 lifespan 시점에 참조 — 테스트에서 monkeypatch 가능."""
import os
from pathlib import Path

SERIAL_PORT = os.getenv("EFB_SERIAL_PORT")            # 미설정 → 모의 GW
SERIAL_BAUD = int(os.getenv("EFB_SERIAL_BAUD", "921600"))
DATA_PATH = Path(os.getenv("EFB_DATA", "data/state.json"))
LINK_TIMEOUT = float(os.getenv("EFB_LINK_TIMEOUT", "6.0"))
```

`server/app/main.py`:
```python
"""E-FairBoard 중앙 관리 서버.

실행: uv run fastapi dev app/main.py   (기본: 모의 게이트웨이)
실물: EFB_SERIAL_PORT=/dev/tty.usbserial-XXXX uv run fastapi dev app/main.py
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import config
from app.api import deploy as deploy_api
from app.api import nodes as nodes_api
from app.api import posts as posts_api
from app.api import stats as stats_api
from app.api import templates as templates_api
from app.bridge.gateway_link import GatewayLink
from app.core.deploy import deploy_post
from app.core.scheduler import DeployScheduler
from app.core.state import StateStore
from app.protocol.packet import Packet

log = logging.getLogger(__name__)


def build_transport():
    if config.SERIAL_PORT:
        from app.bridge.transport import SerialTransport
        log.info("SerialTransport %s @%d", config.SERIAL_PORT, config.SERIAL_BAUD)
        return SerialTransport(config.SERIAL_PORT, config.SERIAL_BAUD)
    from sim.fake_gateway import FakeGatewayTransport
    log.info("모의 게이트웨이 모드 (EFB_SERIAL_PORT 미설정)")
    return FakeGatewayTransport()


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = StateStore(config.DATA_PATH)

    def on_event(pkt: Packet) -> None:
        node = store.nodes.get(pkt.src)
        if node:
            node.online = True
            node.last_seen = time.time()

    link = GatewayLink(build_transport(), timeout=config.LINK_TIMEOUT,
                       on_event=on_event)
    await link.start()

    async def deploy_by_id(post_id: str) -> None:
        post = store.posts.get(post_id)
        if post:
            await deploy_post(link, store, post)

    scheduler = DeployScheduler(deploy_by_id)
    scheduler.start(store)

    app.state.store, app.state.link, app.state.scheduler = store, link, scheduler
    yield
    scheduler.shutdown()
    await link.stop()


app = FastAPI(title="E-FairBoard Server", lifespan=lifespan)
for r in (templates_api.router, posts_api.router, deploy_api.router,
          nodes_api.router, stats_api.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
```

`server/app/api/templates.py`:
```python
from dataclasses import asdict

from fastapi import APIRouter

from app.core.templates import TEMPLATES

router = APIRouter(tags=["templates"])


@router.get("/templates")
def list_templates():
    return [asdict(t) for t in TEMPLATES.values()]
```

`server/app/api/posts.py`:
```python
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.state import Post
from app.core.templates import validate_fields

router = APIRouter(tags=["posts"])


class PostIn(BaseModel):
    template_id: int
    fields: dict[int, str] = {}
    qr_url: str | None = None
    target_node_ids: list[int] = []


def _get_post(request: Request, post_id: str) -> Post:
    post = request.app.state.store.posts.get(post_id)
    if post is None:
        raise HTTPException(404, f"post {post_id} 없음")
    return post


def _validate(body: PostIn) -> None:
    try:
        validate_fields(body.template_id, body.fields)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/posts", status_code=201)
def create_post(body: PostIn, request: Request):
    _validate(body)
    store = request.app.state.store
    post = store.new_post(body.template_id, body.fields,
                          body.qr_url, body.target_node_ids)
    return asdict(post)


@router.get("/posts")
def list_posts(request: Request):
    return [asdict(p) for p in request.app.state.store.posts.values()]


@router.get("/posts/{post_id}")
def get_post(post_id: str, request: Request):
    return asdict(_get_post(request, post_id))


@router.put("/posts/{post_id}")
def update_post(post_id: str, body: PostIn, request: Request):
    _validate(body)
    post = _get_post(request, post_id)
    post.template_id = body.template_id
    post.fields = dict(body.fields)
    post.qr_url = body.qr_url
    post.target_node_ids = list(body.target_node_ids)
    request.app.state.store.save()
    return asdict(post)


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: str, request: Request):
    _get_post(request, post_id)
    request.app.state.scheduler.cancel(post_id)
    del request.app.state.store.posts[post_id]
    request.app.state.store.save()
```

`server/app/api/deploy.py`:
```python
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.deploy import deploy_post

router = APIRouter(tags=["deploy"])


class DeployIn(BaseModel):
    node_ids: list[int] | None = None


class ScheduleIn(BaseModel):
    at: datetime
    node_ids: list[int] | None = None


def _get_post(request: Request, post_id: str):
    post = request.app.state.store.posts.get(post_id)
    if post is None:
        raise HTTPException(404, f"post {post_id} 없음")
    return post


@router.post("/posts/{post_id}/deploy")
async def deploy_now(post_id: str, body: DeployIn, request: Request):
    post = _get_post(request, post_id)
    result = await deploy_post(request.app.state.link, request.app.state.store,
                               post, body.node_ids)
    return {"status": result.status, "ok_nodes": result.ok_nodes,
            "failed_nodes": result.failed_nodes}


@router.post("/posts/{post_id}/schedule")
def schedule(post_id: str, body: ScheduleIn, request: Request):
    post = _get_post(request, post_id)
    if body.node_ids is not None:
        post.target_node_ids = list(body.node_ids)
    post.status = "scheduled"
    post.schedule_at = body.at.isoformat()
    request.app.state.store.save()
    request.app.state.scheduler.schedule(post_id, body.at)
    return {"scheduled_at": post.schedule_at}


@router.delete("/posts/{post_id}/schedule")
def cancel_schedule(post_id: str, request: Request):
    post = _get_post(request, post_id)
    request.app.state.scheduler.cancel(post_id)
    post.status = "draft"
    post.schedule_at = None
    request.app.state.store.save()
    return {"cancelled": True}
```

`server/app/api/nodes.py`:
```python
import struct
import time
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from app.bridge.gateway_link import LinkTimeout
from app.protocol.const import GATEWAY_ID, MsgType
from app.protocol.packet import Packet

router = APIRouter(tags=["nodes"])


def _get_node(request: Request, node_id: int):
    node = request.app.state.store.nodes.get(node_id)
    if node is None:
        raise HTTPException(404, f"node {node_id} 없음")
    return node


@router.get("/nodes")
def list_nodes(request: Request):
    return [asdict(n) for n in request.app.state.store.nodes.values()]


@router.post("/nodes/{node_id}/ping")
async def ping(node_id: int, request: Request):
    node = _get_node(request, node_id)
    link = request.app.state.link
    pkt = Packet(src=GATEWAY_ID, dst=node_id, type=MsgType.PING,
                 seq=link.next_seq(node_id))
    try:
        resp = await link.request(pkt, MsgType.PONG)
    except LinkTimeout:
        node.online = False
        request.app.state.store.save()
        raise HTTPException(504, f"node {node_id} 응답 없음")
    batt, rssi = struct.unpack("<Hb", resp.payload[:3])
    node.online, node.last_seen = True, time.time()
    node.batt_mv, node.rssi = batt, rssi
    request.app.state.store.save()
    return {"batt_mv": batt, "rssi": rssi}


@router.post("/nodes/{node_id}/status")
async def status(node_id: int, request: Request):
    node = _get_node(request, node_id)
    link = request.app.state.link
    pkt = Packet(src=GATEWAY_ID, dst=node_id, type=MsgType.STATUS_REQ,
                 seq=link.next_seq(node_id))
    try:
        resp = await link.request(pkt, MsgType.STATUS_RES)
    except LinkTimeout:
        node.online = False
        request.app.state.store.save()
        raise HTTPException(504, f"node {node_id} 응답 없음")
    batt, last_seq, uptime, err = struct.unpack("<HBHB", resp.payload)
    node.online, node.last_seen = True, time.time()
    node.batt_mv, node.err_cnt = batt, err
    request.app.state.store.save()
    return {"batt_mv": batt, "last_seq": last_seq,
            "uptime_s": uptime, "err_cnt": err}
```

`server/app/api/stats.py`:
```python
from dataclasses import asdict

from fastapi import APIRouter, Request

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats(request: Request):
    store = request.app.state.store
    total = store.stats.deploy_success + store.stats.deploy_fail
    return {
        **asdict(store.stats),
        "success_rate": store.stats.deploy_success / total if total else None,
        "nodes_online": sum(1 for n in store.nodes.values() if n.online),
        "nodes_total": len(store.nodes),
    }
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_api.py -v`
Expected: 6 passed

- [ ] **Step 5: 전체 테스트 + 수동 스모크**

Run: `uv run pytest`
Expected: 전체 통과 (Task 2~12 누적, 40+ passed)

Run(수동, 별도 터미널):
```bash
uv run fastapi dev app/main.py
# 다른 터미널:
curl -s localhost:8000/api/health
curl -s -X POST localhost:8000/api/posts -H 'content-type: application/json' \
  -d '{"template_id":0,"fields":{"0":"테스트 공지"},"qr_url":"https://example.com","target_node_ids":[1,2]}'
curl -s -X POST localhost:8000/api/posts/<id>/deploy -H 'content-type: application/json' -d '{}'
curl -s localhost:8000/api/nodes
```
Expected: deploy 응답 `{"status":"deployed","ok_nodes":[1,2],...}`, nodes에 online=true

- [ ] **Step 6: Commit**

```bash
cd ~/e-fairboard-project && git add server/ && git commit -m "feat(server): FastAPI 앱 + REST API (posts·deploy·schedule·nodes·stats)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: PROTOCOL.md TODO 갱신 + server/README + 마무리

**Files:**
- Modify: `docs/PROTOCOL.md`(§10)
- Create: `server/README.md`

**Interfaces:**
- Produces: 서버 구현이 채택한 규약(엔디안·SEQ 롤오버)과 합의 필요 가정(GW 투명 릴레이, §2 헤더 표기)의 문서화.

- [ ] **Step 1: PROTOCOL.md §10 갱신**

`docs/PROTOCOL.md`의 `## 10. 미정·TODO` 섹션을 다음으로 교체:
```markdown
## 10. 미정·TODO
- [ ] KR920 법정 TX 출력 한도 수치 확정
- [ ] 한글 비트맵 폰트(나눔/Galmuri) e-Paper 적용 방식
- [x] SEQ 롤오버 — 서버 구현 기준: 노드별 독립 SEQ, 0xFF→0x00 순환 (2026-07-08)
- [x] 엔디안 — little-endian 채택 (CRC16 wire 인코딩 포함, 서버 구현 기준 — 펌웨어 동일 적용 필요)
- [ ] **서버↔GW 상위 규약 합의 필요**: 서버 구현은 "GW=투명 릴레이(노드 패킷을 시리얼로
      그대로 중계, LoRa stop-and-wait 재전송(§5)은 GW 내부 처리)"로 가정함
- [ ] **§2 표기 정정 확인**: 헤더 필드 합은 7B(VER~LEN), +CRC 2B = 총 9B 오버헤드 —
      본문 "고정 오버헤드 8B 헤더 + 2B CRC = 10B" 문구와 불일치. 서버는 필드 표(7B) 기준 구현
```

- [ ] **Step 2: server/README.md 작성**

`server/README.md`:
```markdown
# E-FairBoard 서버 (준표 / `jp`)

FastAPI 중앙 관리 서버 — 게시물 작성·예약·배포, LoRa 게이트웨이 시리얼 브리지.

## 실행

```bash
cd server && uv sync

# 모의 게이트웨이 모드 (기본 — 하드웨어 불필요, 가상 노드 0x01·0x02)
uv run fastapi dev app/main.py

# 실물 게이트웨이 모드
EFB_SERIAL_PORT=/dev/tty.usbserial-XXXX uv run fastapi dev app/main.py
```

API 문서: http://localhost:8000/docs

## 테스트

```bash
uv run pytest
```

## 구조

| 경로 | 역할 |
|---|---|
| `app/protocol/` | 논리 패킷 코덱(CRC16)·COBS — 순수 함수, 펌웨어 레퍼런스 겸용 |
| `app/bridge/` | Transport 추상(pyserial↔모의 GW 교체점), GatewayLink(프레이밍·SEQ·응답매칭) |
| `app/core/` | 상태(메모리+JSON)·템플릿·배포 오케스트레이터·예약 |
| `app/api/` | REST 라우터 |
| `sim/` | 모의 게이트웨이 + 가상 노드 (실패 주입 지원) |

## 환경변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `EFB_SERIAL_PORT` | (없음) | 설정 시 실물 시리얼, 미설정 시 모의 GW |
| `EFB_SERIAL_BAUD` | 921600 | 시리얼 속도 |
| `EFB_DATA` | data/state.json | 상태 영속 경로 |
| `EFB_LINK_TIMEOUT` | 6.0 | 패킷 응답 대기(초) |

설계 문서: `../docs/superpowers/specs/2026-07-08-server-skeleton-design.md`
```

- [ ] **Step 3: 전체 테스트 최종 확인**

Run: `cd ~/e-fairboard-project/server && uv run pytest`
Expected: 전체 통과, 실패 0

- [ ] **Step 4: Commit**

```bash
cd ~/e-fairboard-project && git add docs/PROTOCOL.md server/README.md && git commit -m "docs: 프로토콜 TODO 갱신(엔디안·SEQ·GW릴레이 가정) + 서버 README

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review 결과 (계획 작성 후 점검)

- **스펙 커버리지**: §3.1→T2-4, §3.2→T5-6, §3.3→T7-8·10-11, §3.4→T12, §3.5→T9, §5 에러→T6(폐기·재연결)·T10(재시도·OFFLINE)·T8(원자적 쓰기), §6 테스트→각 태스크, §7→T1·12, §8→T13. 갭 없음.
- **비범위 확인**: Vue 대시보드·IMG_FRAG·SQLite는 스펙대로 제외.
- **타입 일관성**: `Transport.read()` 무인자 시그니처 통일, ACK payload `[seq, result]`·PONG `<Hb`+status·STATUS_RES `<HBHB` 전 태스크 일치, `deploy_post(link, store, post, node_ids)` 시그니처 T10↔T12 일치.
