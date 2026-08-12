"""실물 시리얼 전송 — LoRa HAT을 USB-UART(COM 포트)로 붙인다.

VirtualTransport 와 같은 바이트 파이프 계약(Transport)만 만족하면, 상위 링크·프레이밍·
배포는 가상/실물을 구분하지 않는다 (스펙 §3). pyserial 은 블로킹이라 asyncio.to_thread 로
감싸 이벤트 루프를 막지 않는다.
"""
import asyncio

import serial

from ..config import Settings
from ..protocol.link import LinkManager
from .base import Transport


class SerialTransport(Transport):
    def __init__(self, port: str, baud: int = 9600) -> None:
        # serial_for_url: 실물 'COM5' 도, 테스트 'loop://' 루프백도 같은 코드로 연다.
        # timeout=0.1 → read 가 최대 0.1초만 블록 → stop() 시 리더 태스크가 곧 풀린다.
        self._ser = serial.serial_for_url(port, baudrate=baud, timeout=0.1)

    async def write(self, data: bytes) -> None:
        await asyncio.to_thread(self._write, bytes(data))

    def _write(self, data: bytes) -> None:
        self._ser.write(data)
        self._ser.flush()

    async def read(self) -> bytes:
        return await asyncio.to_thread(self._read)

    def _read(self) -> bytes:
        # 1바이트 기다렸다가 버퍼에 쌓인 만큼 한 번에 반환. 유휴 시 b'' (10Hz 폴).
        # ponytail: 폴링 방식. 처리량/지연이 문제되면 전용 리더 스레드로 올린다.
        first = self._ser.read(1)
        if not first:
            return b""
        return first + self._ser.read(self._ser.in_waiting)

    async def close(self) -> None:
        self._ser.close()


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
        transport = SerialTransport(settings.serial_port, settings.serial_baud)
        link = LinkManager(transport, ack_timeout_s=settings.ack_timeout_s,
                           retries=settings.link_retries)
        return cls(link, transport)

    async def start(self) -> None:
        await self.link.start()

    async def stop(self) -> None:
        await self.link.stop()
