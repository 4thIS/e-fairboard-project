from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.state import Post
from app.core.templates import validate_fields

router = APIRouter(tags=["posts"])


class PostIn(BaseModel):
    template_id: int
    fields: dict[int, str] = {}
    qr_url: str | None = None
    target_node_ids: list[int] = []


def _get_post(request: Request, post_id: str) -> Post:
    post = request.app.state.store.posts.get(post_id)
    if post is None:
        raise HTTPException(404, f"post {post_id} 없음")
    return post


def _validate(body: PostIn) -> None:
    try:
        validate_fields(body.template_id, body.fields)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/posts", status_code=201)
def create_post(body: PostIn, request: Request):
    _validate(body)
    store = request.app.state.store
    post = store.new_post(body.template_id, body.fields,
                          body.qr_url, body.target_node_ids)
    return asdict(post)


@router.get("/posts")
def list_posts(request: Request):
    return [asdict(p) for p in request.app.state.store.posts.values()]


@router.get("/posts/{post_id}")
def get_post(post_id: str, request: Request):
    return asdict(_get_post(request, post_id))


@router.put("/posts/{post_id}")
def update_post(post_id: str, body: PostIn, request: Request):
    _validate(body)
    post = _get_post(request, post_id)
    post.template_id = body.template_id
    post.fields = dict(body.fields)
    post.qr_url = body.qr_url
    post.target_node_ids = list(body.target_node_ids)
    request.app.state.store.save()
    return asdict(post)


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: str, request: Request):
    _get_post(request, post_id)
    request.app.state.scheduler.cancel(post_id)
    del request.app.state.store.posts[post_id]
    request.app.state.store.save()
