"""게시물 배포 오케스트레이터 (PROTOCOL §4 시퀀스)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.bridge.gateway_link import GatewayLink, LinkTimeout
from app.core.state import Node, Post, StateStore
from app.protocol.const import GATEWAY_ID, AckResult, MsgType
from app.protocol.packet import Packet

log = logging.getLogger(__name__)
RETRIES = 1   # 서버 상위 재시도 — LoRa 구간 재전송(§5)은 GW 담당


class DeployError(RuntimeError):
    """ACK result != OK."""


@dataclass
class DeployResult:
    ok_nodes: list[int] = field(default_factory=list)
    failed_nodes: list[int] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.failed_nodes:
            return "deployed"
        if not self.ok_nodes:
            return "failed"
        return "partial"


async def _send_checked(link: GatewayLink, dst: int, type_: MsgType,
                        payload: bytes) -> None:
    """SEQ 발급→전송→ACK(result=OK) 확인. 타임아웃/오류 시 재시도 후 예외."""
    last_exc: Exception = LinkTimeout("unreachable")
    for _ in range(RETRIES + 1):
        pkt = Packet(src=GATEWAY_ID, dst=dst, type=type_,
                     seq=link.next_seq(dst), payload=payload)
        try:
            resp = await link.request(pkt, MsgType.ACK)
        except LinkTimeout as e:
            last_exc = e
            continue
        if len(resp.payload) >= 2 and resp.payload[1] == AckResult.OK:
            return
        last_exc = DeployError(
            f"{type_.name} ACK result="
            f"{resp.payload[1] if len(resp.payload) > 1 else '?'}")
    raise last_exc


async def _deploy_node(link: GatewayLink, node: Node, post: Post) -> None:
    template_changed = node.template_id != post.template_id
    if template_changed:
        await _send_checked(link, node.node_id, MsgType.SET_TEMPLATE,
                            bytes([post.template_id]))
    for fid in sorted(post.fields):
        text = post.fields[fid].encode()
        await _send_checked(link, node.node_id, MsgType.SET_FIELD,
                            bytes([fid, len(text)]) + text)
    if post.qr_url:
        url = post.qr_url.encode()
        await _send_checked(link, node.node_id, MsgType.SET_QR,
                            bytes([0, len(url)]) + url)
    refresh = 1 if template_changed else 0   # 템플릿 전환=전체갱신(§4)
    await _send_checked(link, node.node_id, MsgType.COMMIT, bytes([refresh]))
    node.template_id = post.template_id


async def deploy_post(link: GatewayLink, store: StateStore, post: Post,
                      node_ids: list[int] | None = None) -> DeployResult:
    ids = node_ids or post.target_node_ids or sorted(store.nodes)
    post.status = "deploying"
    store.save()
    result = DeployResult()
    for nid in ids:
        node = store.nodes.get(nid)
        if node is None:
            log.warning("알 수 없는 노드 0x%02X — 건너뜀", nid)
            result.failed_nodes.append(nid)
            store.stats.deploy_fail += 1
            continue
        try:
            await _deploy_node(link, node, post)
        except (LinkTimeout, DeployError) as e:
            log.warning("노드 0x%02X 배포 실패: %s", nid, e)
            node.online = False
            node.err_cnt += 1
            result.failed_nodes.append(nid)
            store.stats.deploy_fail += 1
            continue
        node.online = True
        node.last_seen = time.time()
        result.ok_nodes.append(nid)
        store.stats.deploy_success += 1
        store.stats.paper_saved += 1
    post.status = result.status
    post.deployed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    store.save()
    return result
