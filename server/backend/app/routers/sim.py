from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_rig, require_token

router = APIRouter(prefix="/api/sim", tags=["sim"],
                   dependencies=[Depends(require_token)])


def _require_rig(rig):
    if rig is None:
        raise HTTPException(status_code=409, detail="not in virtual mode")
    return rig


class SimConfig(BaseModel):
    loss_rate: float | None = None
    airtime_s: float | None = None


class PowerBody(BaseModel):
    powered: bool


@router.get("/config")
def get_config(rig=Depends(get_rig)) -> dict:
    rig = _require_rig(rig)
    return {"loss_rate": rig.channel.loss_rate, "airtime_s": rig.channel.airtime_s}


@router.put("/config")
def put_config(body: SimConfig, rig=Depends(get_rig)) -> dict:
    rig = _require_rig(rig)
    if body.loss_rate is not None:
        rig.channel.loss_rate = body.loss_rate
    if body.airtime_s is not None:
        rig.channel.airtime_s = body.airtime_s
    return {"loss_rate": rig.channel.loss_rate, "airtime_s": rig.channel.airtime_s}


@router.post("/nodes/{node_id}/power")
def set_power(node_id: int, body: PowerBody, rig=Depends(get_rig)) -> dict:
    rig = _require_rig(rig)
    if node_id not in rig.nodes:
        raise HTTPException(status_code=404, detail="node not found")
    rig.nodes[node_id].powered = body.powered
    return {"node_id": node_id, "powered": body.powered}
