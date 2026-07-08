from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth import TokenRegistry
from ..deps import get_tokens

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request,
          tokens: TokenRegistry = Depends(get_tokens)) -> dict:
    if body.password != request.app.state.settings.admin_password:
        raise HTTPException(status_code=401, detail="wrong password")
    return {"token": tokens.issue()}
