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
