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
