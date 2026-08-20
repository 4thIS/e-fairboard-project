"""실물 시리얼 전송 — LoRa HAT을 USB-UART(COM 포트)로 붙인다.

VirtualTransport 와 같은 바이트 파이프 계약(Transport)만 만족하면, 상위 링크·프레이밍·
배포는 가상/실물을 구분하지 않는다 (스펙 §3). pyserial 은 블로킹이라 asyncio.to_thread 로
감싸 이벤트 루프를 막지 않는다.
"""
import asyncio
import time

import serial

from ..config import Settings
from ..protocol.link import LinkManager
from .base import Transport


class SerialTransport(Transport):
    def __init__(self, port: str, baud: int = 9600,
                 fixed_channel: int | None = None) -> None:
        self._port = port
        self._baud = baud
        # serial_for_url: 실물 'COM5' 도, 테스트 'loop://' 루프백도 같은 코드로 연다.
        # timeout=0.1 → read 가 최대 0.1초만 블록 → stop() 시 리더 태스크가 곧 풀린다.
        self._ser = serial.serial_for_url(port, baudrate=baud, timeout=0.1)
        # fixed_channel 이 있으면 HAT 고정전송 모드 — 프레임마다 [FF FF 채널] 봉투를 앞에
        # 붙여 브로드캐스트로 쏜다. 수신 모듈이 봉투를 떼고 프레임만 UART로 내보낸다.
        # (대상 구분은 봉투 주소가 아니라 논리 패킷 DST 로 — PROTOCOL.md §0.)
        self._envelope = (bytes([0xFF, 0xFF, fixed_channel])
                          if fixed_channel is not None else b"")

    async def write(self, data: bytes) -> None:
        await asyncio.to_thread(self._write, self._envelope + bytes(data))

    def _write(self, data: bytes) -> None:
        ser = self._ser
        if ser is None:  # release() 로 포트를 잠깐 놓은 상태 (무선설정 중) — 조용히 버린다
            return
        try:
            ser.write(data)
            ser.flush()
        except serial.SerialException:
            pass

    async def read(self) -> bytes:
        return await asyncio.to_thread(self._read)

    def _read(self) -> bytes:
        # 1바이트 기다렸다가 버퍼에 쌓인 만큼 한 번에 반환. 유휴 시 b'' (10Hz 폴).
        # ponytail: 폴링 방식. 처리량/지연이 문제되면 전용 리더 스레드로 올린다.
        ser = self._ser
        if ser is None:
            time.sleep(0.1)  # release 중 — busy-spin 방지
            return b""
        try:
            first = ser.read(1)
            if not first:
                return b""
            return first + ser.read(ser.in_waiting)
        except serial.SerialException:
            return b""  # release() 가 포트를 닫는 순간 진행 중이던 read

    def release(self) -> None:
        """포트를 잠깐 놓아준다 — 무선설정 도구가 같은 COM 을 설정모드로 열 수 있게.
        진행 중인 read/write 는 위 예외 처리로 조용히 풀린다. 설정 중엔 HAT 이 설정모드라
        어차피 전송이 안 되므로 링크를 멈춰도 안전하다."""
        ser, self._ser = self._ser, None
        if ser is not None:
            try:
                ser.close()
            except serial.SerialException:
                pass

    def reacquire(self) -> None:
        if self._ser is None:
            self._ser = serial.serial_for_url(self._port, baudrate=self._baud, timeout=0.1)

    async def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None


class SerialRig:
    """실물 HAT 조립. SimRig 와 같은 표면(.link/.nodes/.start/.stop)을 노출해
    라우터·배포 서비스가 가상/실물을 구분하지 않는다. 실물 노드의 display_state 는
    서버가 알 수 없으므로 nodes 는 비어 있다(nodes 라우터가 None 으로 처리)."""

    virtual = False

    def __init__(self, link: LinkManager, transport: SerialTransport) -> None:
        self.link = link
        self.transport = transport
        self.nodes: dict = {}

    @classmethod
    def build(cls, settings: Settings) -> "SerialRig":
        channel = settings.serial_lora_channel if settings.serial_fixed_mode else None
        transport = SerialTransport(settings.serial_port, settings.serial_baud,
                                    fixed_channel=channel)
        link = LinkManager(transport, ack_timeout_s=settings.ack_timeout_s,
                           retries=settings.link_retries,
                           commit_ack_timeout_s=settings.commit_ack_timeout_s)
        return cls(link, transport)

    async def start(self) -> None:
        await self.link.start()

    async def stop(self) -> None:
        await self.link.stop()
