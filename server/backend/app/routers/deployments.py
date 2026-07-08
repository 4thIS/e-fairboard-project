from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_rig, get_store, require_token
from ..models import Deployment
from ..services.deploy_service import start_deployment
from ..store import Store

router = APIRouter(prefix="/api/deployments", tags=["deployments"],
                   dependencies=[Depends(require_token)])


class DeployBody(BaseModel):
    post_id: int
    node_ids: list[int] | Literal["all"]
    refresh_mode: Literal[0, 1] = 0


@router.post("", status_code=202)
async def create_deployment(body: DeployBody, store: Store = Depends(get_store),
                            rig=Depends(get_rig)) -> Deployment:
    # async 필수: start_deployment가 실행 중인 이벤트 루프에 태스크를 건다
    if rig is None:
        raise HTTPException(status_code=409, detail="serial mode not implemented")
    node_ids = (sorted(store.state.nodes) if body.node_ids == "all"
                else body.node_ids)
    try:
        return start_deployment(store, rig, post_id=body.post_id,
                                node_ids=node_ids,
                                refresh_mode=body.refresh_mode, trigger="manual")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{deployment_id}")
def get_deployment(deployment_id: int,
                   store: Store = Depends(get_store)) -> Deployment:
    dep = store.state.deployments.get(deployment_id)
    if dep is None:
        raise HTTPException(status_code=404, detail="deployment not found")
    return dep


@router.get("")
def list_deployments(store: Store = Depends(get_store)) -> list[Deployment]:
    return sorted(store.state.deployments.values(),
                  key=lambda d: d.id, reverse=True)
