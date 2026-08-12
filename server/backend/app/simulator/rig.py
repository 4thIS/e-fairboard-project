from ..config import Settings
from ..protocol.link import LinkManager
from ..transport.virtual import virtual_pair
from .channel import VirtualChannel
from .gateway import VirtualGateway
from .node import VirtualNode

NODE_IDS = (0x01, 0x02)


class SimRig:
    """가상 모드 전체 조립 — lifespan과 테스트가 공용 (스펙 §3)."""

    virtual = True  # SerialRig(False)와 구분 — sim 라우터가 실물 모드를 거른다

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
