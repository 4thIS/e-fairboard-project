"""인메모리 상태 + JSON 영속 (ARCHITECTURE §6: MVP는 DB 없음)."""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Node:
    node_id: int
    name: str
    online: bool = False
    last_seen: float | None = None     # epoch 초
    batt_mv: int | None = None
    rssi: int | None = None
    err_cnt: int = 0
    template_id: int | None = None     # 마지막 COMMIT 성공 템플릿


@dataclass
class Post:
    id: str
    template_id: int
    fields: dict[int, str] = field(default_factory=dict)
    qr_url: str | None = None
    target_node_ids: list[int] = field(default_factory=list)
    status: str = "draft"   # draft|scheduled|deploying|deployed|partial|failed
    schedule_at: str | None = None     # ISO8601
    deployed_at: str | None = None


@dataclass
class Stats:
    deploy_success: int = 0
    deploy_fail: int = 0
    paper_saved: int = 0


DEFAULT_NODES = {0x01: "노드1", 0x02: "노드2"}


class StateStore:
    def __init__(self, path: Path | str):
        self._path = Path(path)
        self.nodes: dict[int, Node] = {}
        self.posts: dict[str, Post] = {}
        self.stats = Stats()
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self.nodes = {nid: Node(nid, name) for nid, name in DEFAULT_NODES.items()}
            return
        raw = json.loads(self._path.read_text())
        self.nodes = {int(k): Node(**v) for k, v in raw["nodes"].items()}
        self.posts = {
            k: Post(**{**v, "fields": {int(fk): fv for fk, fv in v["fields"].items()}})
            for k, v in raw["posts"].items()}
        self.stats = Stats(**raw["stats"])

    def save(self) -> None:
        raw = {
            "nodes": {str(k): asdict(v) for k, v in self.nodes.items()},
            "posts": {k: asdict(v) for k, v in self.posts.items()},
            "stats": asdict(self.stats),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=1))
        os.replace(tmp, self._path)   # 원자적 교체

    def new_post(self, template_id: int, fields: dict[int, str],
                 qr_url: str | None, target_node_ids: list[int]) -> Post:
        post = Post(id=uuid.uuid4().hex[:8], template_id=template_id,
                    fields=dict(fields), qr_url=qr_url,
                    target_node_ids=list(target_node_ids))
        self.posts[post.id] = post
        self.save()
        return post
