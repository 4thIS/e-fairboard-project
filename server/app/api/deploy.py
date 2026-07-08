from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.deploy import deploy_post

router = APIRouter(tags=["deploy"])


class DeployIn(BaseModel):
    node_ids: list[int] | None = None


class ScheduleIn(BaseModel):
    at: datetime
    node_ids: list[int] | None = None


def _get_post(request: Request, post_id: str):
    post = request.app.state.store.posts.get(post_id)
    if post is None:
        raise HTTPException(404, f"post {post_id} 없음")
    return post


@router.post("/posts/{post_id}/deploy")
async def deploy_now(post_id: str, body: DeployIn, request: Request):
    post = _get_post(request, post_id)
    result = await deploy_post(request.app.state.link, request.app.state.store,
                               post, body.node_ids)
    return {"status": result.status, "ok_nodes": result.ok_nodes,
            "failed_nodes": result.failed_nodes}


@router.post("/posts/{post_id}/schedule")
def schedule(post_id: str, body: ScheduleIn, request: Request):
    post = _get_post(request, post_id)
    if body.node_ids is not None:
        post.target_node_ids = list(body.node_ids)
    post.status = "scheduled"
    post.schedule_at = body.at.isoformat()
    request.app.state.store.save()
    request.app.state.scheduler.schedule(post_id, body.at)
    return {"scheduled_at": post.schedule_at}


@router.delete("/posts/{post_id}/schedule")
def cancel_schedule(post_id: str, request: Request):
    post = _get_post(request, post_id)
    request.app.state.scheduler.cancel(post_id)
    post.status = "draft"
    post.schedule_at = None
    request.app.state.store.save()
    return {"cancelled": True}
