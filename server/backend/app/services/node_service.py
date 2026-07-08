import asyncio
from datetime import datetime, timezone

from ..models import StatusSample
from ..protocol.link import LinkError
from ..protocol.packet import MsgType, parse_status_res
from ..store import Store

_OFFLINE_AFTER_MISSES = 2


class NodeMonitor:
    """주기적 STATUS_REQ 폴링 (스펙 §5.6). 실노드 딥슬립 주기와의 동기화는
    펌웨어 팀 협의 항목 — interval_s는 설정으로 주입."""

    def __init__(self, store: Store, rig, interval_s: float) -> None:
        self._store = store
        self._rig = rig
        self._interval_s = interval_s
        self._miss_count: dict[int, int] = {}
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval_s)
            await self.poll_once()

    async def poll_once(self) -> None:
        for node_id in sorted(self._store.state.nodes):
            node = self._store.state.nodes[node_id]
            try:
                res = await self._rig.link.request(
                    node_id, MsgType.STATUS_REQ, expect=MsgType.STATUS_RES)
            except LinkError:
                misses = self._miss_count.get(node_id, 0) + 1
                self._miss_count[node_id] = misses
                if misses >= _OFFLINE_AFTER_MISSES:
                    node.status = "offline"
                continue
            batt_mv, _last_seq, _uptime, _err = parse_status_res(res.payload)
            now = datetime.now(timezone.utc)
            self._miss_count[node_id] = 0
            node.status = "online"
            node.batt_mv = batt_mv
            node.last_seen_at = now
            self._store.add_history(node_id, StatusSample(
                t=now, batt_mv=batt_mv, rssi=node.rssi or 0))
        self._store.save()
