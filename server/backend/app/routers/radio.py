"""무선 셋업 — PC HAT 주파수(채널) 설정 도구 (브링업 편의).

요청마다 포트를 on-demand 로 열고 닫으며, 모듈 Lock 으로 직렬화한다. 설정 모드(M1 점퍼
빼기) 에서만 응답하므로 read 가 설정모드 감지기 역할을 한다.

실물(serial) 모드에선 백엔드 SerialTransport 가 같은 COM 을 상시 점유한다 → 설정 중엔
그 포트를 잠깐 빌린다(_borrow_port). 설정 모드에선 HAT 이 어차피 전송을 못 하므로 안전하다.
"""
import threading
import time
from contextlib import contextmanager

import serial
from serial.tools import list_ports
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_rig, require_token
from ..radio import e22

router = APIRouter(prefix="/api/radio", tags=["radio"],
                   dependencies=[Depends(require_token)])

_lock = threading.Lock()          # 포트 동시 open 방지 (직렬화)
_BAUD = 9600                      # 설정 모드 UART 고정
_NO_CONFIG_HINT = "설정 모드 아님 — M1 점퍼를 빼고(HIGH) 다시 시도하세요"


@contextmanager
def _borrow_port(rig):
    """serial 모드면 백엔드가 잡은 COM 포트를 잠깐 놓아준다(설정 후 되잡음). 가상/미실행이면 통과."""
    transport = getattr(rig, "transport", None)
    if transport is not None and hasattr(transport, "release"):
        transport.release()
        time.sleep(0.15)  # 진행 중이던 read(≤0.1s)가 풀리고 OS 가 포트를 놓을 시간
        try:
            yield
        finally:
            transport.reacquire()
    else:
        yield


class PortReq(BaseModel):
    port: str


class FreqReq(BaseModel):
    port: str
    mhz: float  # 922.125 등 소수점 허용 — 가장 가까운 채널로 반올림


def _read_registers(ser: serial.Serial) -> bytes | None:
    """C1 00 09 → 응답 12바이트(C1 00 09 + 9레지스터). 설정모드 아니면 None."""
    ser.reset_input_buffer()
    ser.write(e22.build_read_cmd())
    ser.flush()
    buf = bytearray()
    deadline = time.time() + 1.0
    while time.time() < deadline and len(buf) < 12:
        chunk = ser.read(12 - len(buf))
        if chunk:
            buf += chunk
            deadline = time.time() + 0.3
    if len(buf) < 12 or buf[0] != 0xC1:
        return None
    return bytes(buf[3:12])


def _open(port: str) -> serial.Serial:
    try:
        return serial.Serial(port, _BAUD, timeout=1)
    except serial.SerialException as exc:
        raise HTTPException(status_code=409,
                            detail=f"포트 열기 실패 — 다른 프로그램이 점유 중? ({exc})")


@router.get("/ports")
def list_serial_ports() -> list[dict]:
    return [{"device": p.device, "description": p.description or ""}
            for p in list_ports.comports()]


@router.post("/read")
def read_registers(req: PortReq, rig=Depends(get_rig)) -> dict:
    with _lock, _borrow_port(rig):
        ser = _open(req.port)
        try:
            reg = _read_registers(ser)
        finally:
            ser.close()
    if reg is None:
        return {"ok": False, "hint": _NO_CONFIG_HINT}
    return {"ok": True, "registers": e22.decode_registers(reg)}


@router.post("/frequency")
def set_frequency(req: FreqReq, rig=Depends(get_rig)) -> dict:
    ch = e22.mhz_to_channel(req.mhz)
    if not (e22.CH_MIN <= ch <= e22.CH_MAX):
        raise HTTPException(
            status_code=422,
            detail=f"{req.mhz}MHz(채널 {ch}) 는 범위 밖입니다 "
                   f"({e22.channel_to_mhz(e22.CH_MIN)}~{e22.channel_to_mhz(e22.CH_MAX)}MHz)")
    with _lock, _borrow_port(rig):
        ser = _open(req.port)
        try:
            before = _read_registers(ser)
            if before is None:
                return {"ok": False, "hint": _NO_CONFIG_HINT}
            ser.reset_input_buffer()
            ser.write(e22.build_write_cmd(before, req.mhz))
            ser.flush()
            time.sleep(0.4)
            ser.read(64)  # 쓰기 에코 소진
            after = _read_registers(ser)
        finally:
            ser.close()
    if after is None:
        return {"ok": False, "hint": "쓰기 후 검증 읽기 실패 — 재시도하세요"}
    ok = after[e22._CH] == e22.mhz_to_channel(req.mhz)
    return {
        "ok": ok,
        "warn": None if e22.in_kr920(req.mhz) else "KR920(920.9~923.3) 범위 밖 채널",
        "before": e22.decode_registers(before),
        "after": e22.decode_registers(after),
    }
