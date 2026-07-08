from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .auth import TokenRegistry
from .config import Settings, get_settings
from .routers import auth as auth_router
from .routers import deployments as deployments_router
from .routers import nodes as nodes_router
from .routers import posts as posts_router
from .routers import schedules as schedules_router
from .routers import sim as sim_router
from .routers import stats as stats_router
from .services.node_service import NodeMonitor
from .services.schedule_service import ScheduleService
from .simulator.rig import NODE_IDS, SimRig
from .store import Store


def _recover_interrupted_deployments(store: Store) -> None:
    """배포 도중 죽었던 흔적 정리 (스펙 §7)."""
    for dep in store.state.deployments.values():
        if dep.status == "running":
            dep.status = "failed"
            dep.finished_at = datetime.now(timezone.utc)
            for target in dep.targets:
                if target.status in ("pending", "sending"):
                    target.status = "failed"
                    target.error = "interrupted"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(Path(settings.data_file))
        store.load()
        _recover_interrupted_deployments(store)
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
        schedule_service = ScheduleService(store, app.state.rig)
        schedule_service.start()
        app.state.schedule_service = schedule_service
        monitor = NodeMonitor(store, app.state.rig,
                              interval_s=settings.status_poll_interval_s)
        if app.state.rig is not None:
            await monitor.start()
        app.state.node_monitor = monitor
        yield
        await monitor.stop()
        schedule_service.shutdown()
        if app.state.rig is not None:
            await app.state.rig.stop()
        store.save()

    app = FastAPI(title="E-FairBoard Server", lifespan=lifespan)
    app.include_router(auth_router.router)
    app.include_router(posts_router.router)
    app.include_router(nodes_router.router)
    app.include_router(sim_router.router)
    app.include_router(deployments_router.router)
    app.include_router(schedules_router.router)
    app.include_router(stats_router.router)

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.exists():  # 프론트 빌드 산출물이 있으면 단일 프로세스 데모 (스펙 §3)
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app
