"""예약 배포 — APScheduler 인메모리 잡 + JSON 영속 포스트에서 기동 시 복원."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from app.core.state import StateStore

log = logging.getLogger(__name__)


class DeployScheduler:
    def __init__(self, deploy_cb: Callable[[str], Awaitable[None]]):
        self._sched = AsyncIOScheduler()
        self._cb = deploy_cb

    def start(self, store: StateStore) -> None:
        self._sched.start()
        now = datetime.now(timezone.utc)
        dirty = False
        for post in store.posts.values():
            if post.status != "scheduled" or not post.schedule_at:
                continue
            at = datetime.fromisoformat(post.schedule_at)
            if at > now:
                self.schedule(post.id, at)
                log.info("예약 복원: %s @ %s", post.id, post.schedule_at)
            else:
                post.status = "failed"   # 서버 다운 중 지나간 예약
                dirty = True
                log.warning("지난 예약 failed 처리: %s @ %s", post.id, post.schedule_at)
        if dirty:
            store.save()

    def schedule(self, post_id: str, at: datetime) -> None:
        self._sched.add_job(self._cb, DateTrigger(run_date=at),
                            args=[post_id], id=post_id, replace_existing=True)

    def cancel(self, post_id: str) -> None:
        if self._sched.get_job(post_id):
            self._sched.remove_job(post_id)

    def has_job(self, post_id: str) -> bool:
        return self._sched.get_job(post_id) is not None

    def shutdown(self) -> None:
        if self._sched.running:
            self._sched.shutdown(wait=False)
