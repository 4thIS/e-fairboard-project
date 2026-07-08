from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..deps import get_store, require_token
from ..models import Schedule
from ..store import Store

router = APIRouter(prefix="/api/schedules", tags=["schedules"],
                   dependencies=[Depends(require_token)])


class ScheduleBody(BaseModel):
    post_id: int
    node_ids: list[int] | Literal["all"]
    run_at: datetime


@router.post("", status_code=201)
def create_schedule(body: ScheduleBody, request: Request,
                    store: Store = Depends(get_store)) -> Schedule:
    service = request.app.state.schedule_service
    node_ids = (sorted(store.state.nodes) if body.node_ids == "all"
                else body.node_ids)
    try:
        return service.add(body.post_id, node_ids, body.run_at)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("")
def list_schedules(store: Store = Depends(get_store)) -> list[Schedule]:
    return sorted(store.state.schedules.values(), key=lambda s: s.run_at)


@router.delete("/{schedule_id}", status_code=204)
def cancel_schedule(schedule_id: int, request: Request) -> Response:
    service = request.app.state.schedule_service
    try:
        service.cancel(schedule_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="schedule not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)
