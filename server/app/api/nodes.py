import struct
import time
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from app.bridge.gateway_link import LinkTimeout
from app.protocol.const import GATEWAY_ID, MsgType
from app.protocol.packet import Packet

router = APIRouter(tags=["nodes"])


def _get_node(request: Request, node_id: int):
    node = request.app.state.store.nodes.get(node_id)
    if node is None:
        raise HTTPException(404, f"node {node_id} 없음")
    return node


@router.get("/nodes")
def list_nodes(request: Request):
    return [asdict(n) for n in request.app.state.store.nodes.values()]


@router.post("/nodes/{node_id}/ping")
async def ping(node_id: int, request: Request):
    node = _get_node(request, node_id)
    link = request.app.state.link
    pkt = Packet(src=GATEWAY_ID, dst=node_id, type=MsgType.PING,
                 seq=link.next_seq(node_id))
    try:
        resp = await link.request(pkt, MsgType.PONG)
    except LinkTimeout:
        node.online = False
        request.app.state.store.save()
        raise HTTPException(504, f"node {node_id} 응답 없음")
    batt, rssi = struct.unpack("<Hb", resp.payload[:3])
    node.online, node.last_seen = True, time.time()
    node.batt_mv, node.rssi = batt, rssi
    request.app.state.store.save()
    return {"batt_mv": batt, "rssi": rssi}


@router.post("/nodes/{node_id}/status")
async def status(node_id: int, request: Request):
    node = _get_node(request, node_id)
    link = request.app.state.link
    pkt = Packet(src=GATEWAY_ID, dst=node_id, type=MsgType.STATUS_REQ,
                 seq=link.next_seq(node_id))
    try:
        resp = await link.request(pkt, MsgType.STATUS_RES)
    except LinkTimeout:
        node.online = False
        request.app.state.store.save()
        raise HTTPException(504, f"node {node_id} 응답 없음")
    batt, last_seq, uptime, err = struct.unpack("<HBHB", resp.payload)
    node.online, node.last_seen = True, time.time()
    node.batt_mv, node.err_cnt = batt, err
    request.app.state.store.save()
    return {"batt_mv": batt, "last_seq": last_seq,
            "uptime_s": uptime, "err_cnt": err}
