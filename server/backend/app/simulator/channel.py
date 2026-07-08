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
