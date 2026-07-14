from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_rig, get_store, require_token
from ..models import NodeInfo, StatusSample
from ..protocol.link import LinkError
from ..protocol.packet import MsgType, parse_pong
from ..store import Store

router = APIRouter(prefix="/api/nodes", tags=["nodes"],
                   dependencies=[Depends(require_token)])


def _get_or_404(store: Store, node_id: int) -> NodeInfo:
    node = store.state.nodes.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="node not found")
    return node


@router.get("")
def list_nodes(store: Store = Depends(get_store),
               rig=Depends(get_rig)) -> list[dict]:
    out = []
    for n in sorted(store.state.nodes.values(), key=lambda n: n.id):
        data = n.model_dump(exclude={"history"}, mode="json")
        data["display_state"] = (
            rig.nodes[n.id].display_state
            if rig is not None and n.id in rig.nodes else None)
        out.append(data)
    return out


@router.get("/{node_id}")
def node_detail(node_id: int, store: Store = Depends(get_store),
                rig=Depends(get_rig)) -> dict:
    node = _get_or_404(store, node_id)
    data = node.model_dump(exclude={"history"}, mode="json")
    data["display_state"] = (
        rig.nodes[node_id].display_state
        if rig is not None and node_id in rig.nodes else None)
    return data


@router.get("/{node_id}/history")
def node_history(node_id: int, store: Store = Depends(get_store)) -> list[StatusSample]:
    return _get_or_404(store, node_id).history


@router.post("/{node_id}/ping")
async def ping_node(node_id: int, store: Store = Depends(get_store),
                    rig=Depends(get_rig)) -> dict:
    node = _get_or_404(store, node_id)
    if rig is None:
        raise HTTPException(status_code=409, detail="serial mode not implemented")
    try:
        pong = await rig.link.request(node_id, MsgType.PING, expect=MsgType.PONG)
    except LinkError:
        node.status = "offline"
        store.save()
        return {"ok": False}
    batt_mv, rssi, _status = parse_pong(pong.payload)
    now = datetime.now(timezone.utc)
    node.status = "online"
    node.batt_mv = batt_mv
    node.rssi = rssi
    node.last_seen_at = now
    store.add_history(node_id, StatusSample(t=now, batt_mv=batt_mv, rssi=rssi))
    store.save()
    return {"ok": True, "batt_mv": batt_mv, "rssi": rssi}
