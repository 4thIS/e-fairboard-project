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
