import asyncio
from datetime import datetime, timedelta, timezone

from app.core.scheduler import DeployScheduler
from app.core.state import StateStore


def utcnow():
    return datetime.now(timezone.utc)


async def test_예약시각에_콜백_실행(tmp_path):
    called = []

    async def cb(post_id):
        called.append(post_id)

    sched = DeployScheduler(cb)
    sched.start(StateStore(tmp_path / "s.json"))
    sched.schedule("abc123", utcnow() + timedelta(seconds=0.1))
    assert sched.has_job("abc123")
    await asyncio.sleep(0.3)
    assert called == ["abc123"]
    assert not sched.has_job("abc123")
    sched.shutdown()


async def test_취소하면_실행_안됨(tmp_path):
    called = []

    async def cb(post_id):
        called.append(post_id)

    sched = DeployScheduler(cb)
    sched.start(StateStore(tmp_path / "s.json"))
    sched.schedule("abc123", utcnow() + timedelta(seconds=0.1))
    sched.cancel("abc123")
    await asyncio.sleep(0.2)
    assert called == []
    sched.shutdown()


async def test_기동시_미래예약_재등록_과거예약은_failed(tmp_path):
    store = StateStore(tmp_path / "s.json")
    future = store.new_post(0, {}, None, [])
    future.status = "scheduled"
    future.schedule_at = (utcnow() + timedelta(hours=1)).isoformat()
    past = store.new_post(0, {}, None, [])
    past.status = "scheduled"
    past.schedule_at = (utcnow() - timedelta(hours=1)).isoformat()
    store.save()

    async def cb(post_id):
        pass

    sched = DeployScheduler(cb)
    sched.start(store)
    assert sched.has_job(future.id)
    assert not sched.has_job(past.id)
    assert store.posts[past.id].status == "failed"
    sched.shutdown()
