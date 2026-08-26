import os
from pathlib import Path
from typing import Literal

from .models import AppState, NodeInfo, StatusSample

HISTORY_MAX = 2000  # 노드당 이력 링버퍼 한도 (스펙 §5.3)


class Store:
    """메모리 상태 + JSON 원자적 스냅샷 (스펙 §5.3). DB 없음."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self.state = AppState()

    def load(self) -> None:
        if not self._path.exists():
            self.state = AppState()
            return
        try:
            self.state = AppState.model_validate_json(
                self._path.read_text(encoding="utf-8"))
        except ValueError:
            backup = self._path.with_suffix(self._path.suffix + ".bak")
            os.replace(self._path, backup)
            self.state = AppState()

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(self.state.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def next_id(self, counter: Literal["post", "deployment", "schedule"]) -> int:
        attr = f"next_{counter}_id"
        value = getattr(self.state, attr)
        setattr(self.state, attr, value + 1)
        return value

    def add_history(self, node_id: int, sample: StatusSample) -> None:
        history = self.state.nodes[node_id].history
        history.append(sample)
        if len(history) > HISTORY_MAX:
            del history[: len(history) - HISTORY_MAX]

    def seed_nodes(self, node_ids: list[int]) -> None:
        for nid in node_ids:
            if nid not in self.state.nodes:
                self.state.nodes[nid] = NodeInfo(id=nid, name=f"노드 {nid}")

    def add_node(self, nid: int, name: str) -> NodeInfo:
        node = NodeInfo(id=nid, name=name)
        self.state.nodes[nid] = node
        return node

    def remove_node(self, nid: int) -> None:
        self.state.nodes.pop(nid, None)
