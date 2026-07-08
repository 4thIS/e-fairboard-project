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
