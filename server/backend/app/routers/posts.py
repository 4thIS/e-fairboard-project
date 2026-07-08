from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from ..deps import get_store, require_token
from ..models import Post
from ..protocol.templates import as_dict
from ..schemas import PostCreate
from ..store import Store

router = APIRouter(prefix="/api", tags=["posts"],
                   dependencies=[Depends(require_token)])


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/templates")
def list_templates() -> list[dict]:
    return as_dict()


@router.get("/posts")
def list_posts(store: Store = Depends(get_store)) -> list[Post]:
    return sorted(store.state.posts.values(), key=lambda p: p.id, reverse=True)


@router.post("/posts", status_code=201)
def create_post(body: PostCreate, store: Store = Depends(get_store)) -> Post:
    pid = store.next_id("post")
    post = Post(id=pid, created_at=_now(), updated_at=_now(), **body.model_dump())
    store.state.posts[pid] = post
    store.save()
    return post


def _get_or_404(store: Store, post_id: int) -> Post:
    post = store.state.posts.get(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return post


@router.get("/posts/{post_id}")
def get_post(post_id: int, store: Store = Depends(get_store)) -> Post:
    return _get_or_404(store, post_id)


@router.put("/posts/{post_id}")
def update_post(post_id: int, body: PostCreate,
                store: Store = Depends(get_store)) -> Post:
    post = _get_or_404(store, post_id)
    updated = post.model_copy(update={**body.model_dump(), "updated_at": _now()})
    store.state.posts[post_id] = updated
    store.save()
    return updated


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: int, store: Store = Depends(get_store)) -> Response:
    _get_or_404(store, post_id)
    del store.state.posts[post_id]
    store.save()
    return Response(status_code=204)
