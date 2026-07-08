import asyncio
from datetime import datetime, timezone
from typing import Literal

from ..models import Deployment, DeployTarget, Post
from ..protocol.link import LinkError
from ..protocol.packet import MsgType, build_set_field, build_set_qr
from ..simulator.rig import SimRig
from ..store import Store


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_packet_plan(post: Post, refresh_mode: int) -> list[tuple[MsgType, bytes]]:
    """게시물 → SET_TEMPLATE → SET_FIELD×n → SET_QR? → COMMIT (PROTOCOL.md §4)."""
    plan: list[tuple[MsgType, bytes]] = [
        (MsgType.SET_TEMPLATE, bytes([post.template_id]))]
    for field_id in sorted(post.fields, key=int):
        plan.append((MsgType.SET_FIELD,
                     build_set_field(int(field_id), post.fields[field_id])))
    if post.qr_url:
        plan.append((MsgType.SET_QR, build_set_qr(post.qr_url)))
    plan.append((MsgType.COMMIT, bytes([refresh_mode])))
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
            for msg_type, payload in plan:
                target.attempts += 1
                await rig.link.request(target.node_id, msg_type, payload,
                                       expect=MsgType.ACK)
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
