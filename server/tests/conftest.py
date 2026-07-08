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
