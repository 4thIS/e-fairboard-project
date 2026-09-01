import asyncio
from datetime import datetime, timezone
from typing import Literal

from ..models import Deployment, DeployTarget, Post
from ..protocol.link import LinkError
from ..protocol.packet import (
    FRAG_SINGLE, MsgType, build_set_field_fragments, build_set_qr,
)
from ..simulator.rig import SimRig
from ..store import Store


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_packet_plan(post: Post, refresh_mode: int) -> list[tuple[MsgType, bytes, int]]:
    """게시물 → SET_TEMPLATE → SET_FIELD×n → SET_QR? → COMMIT (PROTOCOL.md §4).

    각 스텝은 (타입, payload, frag). 긴 필드는 여러 SET_FIELD 조각으로 전개된다(§3.2 분할) —
    조각마다 frag(인덱스|LAST). 198B 이하 필드는 조각 하나(FRAG_SINGLE)라 기존과 동일.
    """
    plan: list[tuple[MsgType, bytes, int]] = [
        (MsgType.SET_TEMPLATE, bytes([post.template_id]), FRAG_SINGLE)]
    for field_id in sorted(post.fields, key=int):
        for payload, frag in build_set_field_fragments(int(field_id), post.fields[field_id]):
            plan.append((MsgType.SET_FIELD, payload, frag))
    if post.qr_url:
        plan.append((MsgType.SET_QR, build_set_qr(post.qr_url), FRAG_SINGLE))
    plan.append((MsgType.COMMIT, bytes([refresh_mode]), FRAG_SINGLE))
    return plan


def start_deployment(store: Store, rig: SimRig, *, post_id: int,
                     node_ids: list[int], refresh_mode: int,
                     trigger: Literal["manual", "scheduled"]) -> Deployment:
    if post_id not in store.state.posts:
        raise ValueError("post not found")
    for nid in node_ids:
        if nid not in store.state.nodes:
            raise ValueError(f"node {nid} not found")
    dep = Deployment(
        id=store.next_id("deployment"), post_id=post_id, trigger=trigger,
        refresh_mode=refresh_mode, created_at=_now(),
        targets=[DeployTarget(node_id=nid) for nid in node_ids])
    store.state.deployments[dep.id] = dep
    store.save()
    asyncio.get_running_loop().create_task(run_deployment(store, rig, dep.id))
    return dep


async def run_deployment(store: Store, rig: SimRig, deployment_id: int) -> None:
    dep = store.state.deployments[deployment_id]
    post = store.state.posts[dep.post_id]
    plan = build_packet_plan(post, dep.refresh_mode)
    for target in dep.targets:  # 순차 유니캐스트 (스펙 §5.5)
        target.status = "sending"
        store.save()
        try:
            for i, (msg_type, payload, frag) in enumerate(plan, start=1):
                target.step_name = msg_type.name
                target.step_index = i
                target.step_total = len(plan)
                target.attempts += 1
                store.save()  # 1초 폴링이 단계 진행을 보게 한다 (스펙 §6.3)
                await rig.link.request(target.node_id, msg_type, payload,
                                       expect=MsgType.ACK, frag=frag)
            target.status = "success"
            target.acked_at = _now()
            node = store.state.nodes[target.node_id]
            node.current_post_id = post.id
            node.status = "online"
            node.last_seen_at = _now()
        except LinkError as exc:
            target.status = "failed"
            target.error = str(exc)
            store.state.nodes[target.node_id].status = "offline"
        store.save()
    statuses = {t.status for t in dep.targets}
    dep.status = ("success" if statuses == {"success"}
                  else "failed" if statuses == {"failed"} else "partial")
    dep.finished_at = _now()
    store.save()
