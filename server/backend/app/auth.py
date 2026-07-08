import secrets


class TokenRegistry:
    """서버 메모리 토큰 — 재시작 시 전부 무효(재로그인, 스펙 §5.4)."""

    def __init__(self) -> None:
        self._tokens: set[str] = set()

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens.add(token)
        return token

    def is_valid(self, token: str) -> bool:
        return token in self._tokens
