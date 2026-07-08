from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from .auth import TokenRegistry
from .config import Settings, get_settings
from .routers import auth as auth_router
from .routers import nodes as nodes_router
from .routers import posts as posts_router
from .routers import sim as sim_router
from .simulator.rig import NODE_IDS, SimRig
from .store import Store


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(Path(settings.data_file))
        store.load()
        app.state.settings = settings
        app.state.store = store
        app.state.tokens = TokenRegistry()
        if settings.transport_mode == "virtual":
            rig = SimRig.build(settings)
            await rig.start()
            app.state.rig = rig
            store.seed_nodes(list(NODE_IDS))
        else:  # serial 모드 — 하드웨어 전환 계획(스펙 §10)에서 구현
            app.state.rig = None
        store.save()
        yield
        if app.state.rig is not None:
            await app.state.rig.stop()
        store.save()

    app = FastAPI(title="E-FairBoard Server", lifespan=lifespan)
    app.include_router(auth_router.router)
    app.include_router(posts_router.router)
    app.include_router(nodes_router.router)
    app.include_router(sim_router.router)
    return app
