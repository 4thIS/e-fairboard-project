from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import TokenRegistry
from .store import Store

_bearer = HTTPBearer(auto_error=False)


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_rig(request: Request):
    return getattr(request.app.state, "rig", None)


def get_tokens(request: Request) -> TokenRegistry:
    return request.app.state.tokens


def require_token(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    tokens: TokenRegistry = request.app.state.tokens
    if cred is None or not tokens.is_valid(cred.credentials):
        raise HTTPException(status_code=401, detail="invalid or missing token")
