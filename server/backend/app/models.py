from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Post(BaseModel):
    id: int
    title: str
    template_id: int
    fields: dict[str, str] = Field(default_factory=dict)  # field_id(str) -> text
    qr_url: str = ""
    created_at: datetime
    updated_at: datetime


class StatusSample(BaseModel):
    t: datetime
    batt_mv: int
    rssi: int


class NodeInfo(BaseModel):
    id: int
    name: str
    status: Literal["online", "offline", "unknown"] = "unknown"
    batt_mv: int | None = None
    rssi: int | None = None
    last_seen_at: datetime | None = None
    current_post_id: int | None = None
    history: list[StatusSample] = Field(default_factory=list)


class DeployTarget(BaseModel):
    node_id: int
    status: Literal["pending", "sending", "success", "failed"] = "pending"
    attempts: int = 0
    error: str = ""
    acked_at: datetime | None = None


class Deployment(BaseModel):
    id: int
    post_id: int
    status: Literal["running", "success", "partial", "failed"] = "running"
    trigger: Literal["manual", "scheduled"] = "manual"
    refresh_mode: int = 0  # 0=부분, 1=전체
    created_at: datetime
    finished_at: datetime | None = None
    targets: list[DeployTarget] = Field(default_factory=list)


class Schedule(BaseModel):
    id: int
    post_id: int
    node_ids: list[int]
    run_at: datetime
    status: Literal["pending", "done", "cancelled"] = "pending"
    created_at: datetime


class AppState(BaseModel):
    posts: dict[int, Post] = Field(default_factory=dict)
    nodes: dict[int, NodeInfo] = Field(default_factory=dict)
    deployments: dict[int, Deployment] = Field(default_factory=dict)
    schedules: dict[int, Schedule] = Field(default_factory=dict)
    next_post_id: int = 1
    next_deployment_id: int = 1
    next_schedule_id: int = 1
