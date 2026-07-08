from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..models import Schedule
from ..store import Store
from .deploy_service import start_deployment


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScheduleService:
    """일회성 예약 — 인메모리 jobstore, 부팅 시 JSON에서 pending 재등록 (스펙 §5.3)."""

    def __init__(self, store: Store, rig) -> None:
        self._store = store
        self._rig = rig
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        self._scheduler.start()
        for sched in self._store.state.schedules.values():
            if sched.status == "pending":
                self._register(sched)

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def _register(self, sched: Schedule) -> None:
        run_at = sched.run_at
        if run_at <= _now():  # 서버 꺼진 사이 지난 예약 → 즉시 실행으로 보정
            run_at = _now() + timedelta(seconds=1)
        self._scheduler.add_job(self._fire, "date", run_date=run_at,
                                args=[sched.id], id=f"schedule-{sched.id}")

    def add(self, post_id: int, node_ids: list[int], run_at: datetime) -> Schedule:
        if post_id not in self._store.state.posts:
            raise ValueError("post not found")
        for nid in node_ids:
            if nid not in self._store.state.nodes:
                raise ValueError(f"node {nid} not found")
        sched = Schedule(id=self._store.next_id("schedule"), post_id=post_id,
                         node_ids=node_ids, run_at=run_at, created_at=_now())
        self._store.state.schedules[sched.id] = sched
        self._store.save()
        self._register(sched)
        return sched

    def cancel(self, schedule_id: int) -> None:
        sched = self._store.state.schedules.get(schedule_id)
        if sched is None:
            raise KeyError(schedule_id)
        if sched.status != "pending":
            raise ValueError("only pending schedules can be cancelled")
        job = self._scheduler.get_job(f"schedule-{schedule_id}")
        if job is not None:
            job.remove()
        sched.status = "cancelled"
        self._store.save()

    async def _fire(self, schedule_id: int) -> None:
        sched = self._store.state.schedules.get(schedule_id)
        if sched is None or sched.status != "pending":
            return
        sched.status = "done"
        if sched.post_id in self._store.state.posts:
            start_deployment(self._store, self._rig, post_id=sched.post_id,
                             node_ids=sched.node_ids, refresh_mode=0,
                             trigger="scheduled")
        self._store.save()
