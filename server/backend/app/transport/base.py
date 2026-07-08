from abc import ABC, abstractmethod


class Transport(ABC):
    """바이트 스트림 추상 — 상위(link)는 가상/시리얼을 구분하지 않는다 (스펙 §3)."""

    @abstractmethod
    async def write(self, data: bytes) -> None: ...

    @abstractmethod
    async def read(self) -> bytes: ...

    async def close(self) -> None:
        return None
